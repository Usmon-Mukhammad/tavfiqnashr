/** Exercises worker/src/worker.js against a mocked GitHub API. Run: node tools/test-worker.mjs */
import assert from "node:assert/strict";
import cryptoNode from "node:crypto";

const PASSWORD = "a-very-long-test-password";
const ITER = 210000;
const salt = cryptoNode.randomBytes(16);
const digest = cryptoNode.pbkdf2Sync(PASSWORD, salt, ITER, 32, "sha256");

const env = {
  ADMIN_USERNAME: "nashriyot",
  ADMIN_PASSWORD_HASH: `pbkdf2$${ITER}$${salt.toString("base64")}$${digest.toString("base64")}`,
  SESSION_SECRET: "test-session-secret-value",
  GITHUB_TOKEN: "ghp_TESTTOKEN_SHOULD_NEVER_LEAK",
  GITHUB_OWNER: "Usmon-Mukhammad",
  GITHUB_REPO: "tavfiqnashr",
  GITHUB_BRANCH: "main",
  SESSION_HOURS: "8",
};

// ---- mock GitHub -----------------------------------------------------------
const files = new Map([
  ["content/blog/uz/tasavvuf-nima.md",
    "title: Tasavvuf nima?\ndate: 2026-09-14\ndescription: Ta’riflar.\nsource: Kitob\n\nMatn boshlanadi.\n"],
]);
const calls = [];
globalThis.fetch = async (url, init = {}) => {
  const u = new URL(url);
  calls.push({ url: u.pathname, method: init.method || "GET", auth: init.headers?.authorization,
    body: init.body ? JSON.parse(init.body) : null });
  const m = u.pathname.match(/\/repos\/[^/]+\/[^/]+\/contents\/(.+)$/);
  const path = m ? decodeURIComponent(m[1]) : "";
  const ok = (body) => new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });

  if (path.startsWith("content/blog/") && !path.endsWith(".md")) {
    const lang = path.split("/")[2];
    return ok([...files.keys()].filter((f) => f.startsWith(`content/blog/${lang}/`))
      .map((f) => ({ name: f.split("/").pop(), type: "file" })));
  }
  if ((init.method || "GET") === "GET") {
    if (!files.has(path)) return new Response("{}", { status: 404 });
    return ok({ sha: "sha-" + path, content: Buffer.from(files.get(path), "utf8").toString("base64") });
  }
  if (init.method === "PUT") {
    files.set(path, Buffer.from(JSON.parse(init.body).content, "base64").toString("utf8"));
    return ok({ content: { path } });
  }
  if (init.method === "DELETE") { files.delete(path); return ok({}); }
  return new Response("{}", { status: 400 });
};

const { default: worker } = await import("../worker/src/worker.js");
const call = (path, init = {}) =>
  worker.fetch(new Request("https://tavfiqnashr.uz/api/admin" + path, init), env);
const post = (path, body, headers = {}) =>
  call(path, { method: "PUT", body: JSON.stringify(body), headers: { "x-requested-with": "tn-admin", ...headers } });

let pass = 0;
const t = async (name, fn) => { await fn(); console.log("  ok  " + name); pass++; };

// ---- auth ------------------------------------------------------------------
await t("rejects wrong password", async () => {
  const r = await call("/login", { method: "POST", body: JSON.stringify({ username: "nashriyot", password: "wrong" }) });
  assert.equal(r.status, 401);
  assert.equal(r.headers.get("set-cookie"), null);
});

await t("rejects wrong username", async () => {
  const r = await call("/login", { method: "POST", body: JSON.stringify({ username: "someone", password: PASSWORD }) });
  assert.equal(r.status, 401);
});

let cookie;
await t("accepts correct credentials and sets a hardened cookie", async () => {
  const r = await call("/login", { method: "POST", body: JSON.stringify({ username: "nashriyot", password: PASSWORD }) });
  assert.equal(r.status, 200);
  const sc = r.headers.get("set-cookie");
  assert.match(sc, /HttpOnly/); assert.match(sc, /Secure/); assert.match(sc, /SameSite=Strict/);
  cookie = sc.split(";")[0];
});

await t("blocks unauthenticated API access", async () => {
  assert.equal((await call("/posts")).status, 401);
});

await t("rejects a forged session signature", async () => {
  const bad = cookie.replace(/.$/, (c) => (c === "A" ? "B" : "A"));
  assert.equal((await call("/posts", { headers: { cookie: bad } })).status, 401);
});

await t("rejects an expired session", async () => {
  const short = { ...env, SESSION_HOURS: "-1" };
  const r = await worker.fetch(new Request("https://tavfiqnashr.uz/api/admin/login",
    { method: "POST", body: JSON.stringify({ username: "nashriyot", password: PASSWORD }) }), short);
  const expired = r.headers.get("set-cookie").split(";")[0];
  assert.equal((await worker.fetch(new Request("https://tavfiqnashr.uz/api/admin/posts",
    { headers: { cookie: expired } }), short)).status, 401);
});

await t("blocks writes without the CSRF header", async () => {
  const r = await call("/posts/uz/x-post", {
    method: "PUT", headers: { cookie },
    body: JSON.stringify({ title: "T", date: "2026-01-01", description: "D", body: "B" }),
  });
  assert.equal(r.status, 403);
});

// ---- content ---------------------------------------------------------------
await t("lists posts per language", async () => {
  const d = await (await call("/posts", { headers: { cookie } })).json();
  assert.deepEqual(d.uz, ["tasavvuf-nima"]);
  assert.deepEqual(d.ru, []);
});

await t("reads an existing post and splits front matter from body", async () => {
  const d = await (await call("/posts/uz/tasavvuf-nima", { headers: { cookie } })).json();
  assert.equal(d.title, "Tasavvuf nima?");
  assert.equal(d.source, "Kitob");
  assert.equal(d.body.trim(), "Matn boshlanadi.");
});

await t("rejects a bad slug", async () => {
  const r = await post("/posts/uz/Bad_Slug", { title: "T", date: "2026-01-01", description: "D", body: "B" }, { cookie });
  assert.equal(r.status, 400);
});

await t("rejects invalid front-matter values", async () => {
  for (const bad of [
    { title: "", date: "2026-01-01", description: "D", body: "B" },
    { title: "T", date: "01-01-2026", description: "D", body: "B" },
    { title: "T", date: "2026-01-01", description: "D", body: "" },
    { title: "Two\nlines", date: "2026-01-01", description: "D", body: "B" },
  ]) {
    const r = await post("/posts/uz/some-slug", bad, { cookie });
    assert.equal(r.status, 400, JSON.stringify(bad));
  }
});

await t("creates a post with correct front matter", async () => {
  calls.length = 0;
  const r = await post("/posts/ru/novaya-statya", {
    title: "Новая статья", date: "2026-10-11", description: "Описание.",
    source: "«Книга»", tags: "Тест", body: "## Заголовок\n\nТекст.",
  }, { cookie });
  assert.equal(r.status, 200);
  const md = files.get("content/blog/ru/novaya-statya.md");
  assert.equal(md.split("\n\n")[0],
    "title: Новая статья\ndate: 2026-10-11\ndescription: Описание.\nsource: «Книга»\ntags: Тест");
  assert.match(md, /## Заголовок/);
  const created = calls.filter((c) => c.method === "PUT").pop();
  assert.equal("sha" in created.body, false, "a new file must not send a sha");
});

await t("updates an existing post using its sha", async () => {
  calls.length = 0;
  const r = await post("/posts/uz/tasavvuf-nima", {
    title: "Tasavvuf nima? (yangilandi)", date: "2026-09-14", description: "D", body: "Yangi matn.",
  }, { cookie });
  assert.equal(r.status, 200);
  const put = calls.find((c) => c.method === "PUT");
  assert.ok(put, "expected a PUT to GitHub");
  assert.equal(put.body.sha, "sha-content/blog/uz/tasavvuf-nima.md",
    "an update must send the existing file sha or GitHub rejects it");
  assert.equal(put.body.branch, "main");
  assert.match(files.get("content/blog/uz/tasavvuf-nima.md"), /yangilandi/);
});

await t("deletes a post", async () => {
  const r = await call("/posts/ru/novaya-statya", { method: "DELETE", headers: { cookie, "x-requested-with": "tn-admin" } });
  assert.equal(r.status, 200);
  assert.equal(files.has("content/blog/ru/novaya-statya.md"), false);
});

// ---- secrets ---------------------------------------------------------------
await t("never returns the GitHub token to the browser", async () => {
  for (const p of ["/posts", "/posts/uz/tasavvuf-nima", "/session"]) {
    const body = await (await call(p, { headers: { cookie } })).text();
    assert.equal(body.includes(env.GITHUB_TOKEN), false, p);
  }
  assert.ok(calls.every((c) => !c.auth || c.auth === `Bearer ${env.GITHUB_TOKEN}`));
});

await t("fails closed when a secret is missing", async () => {
  const r = await worker.fetch(new Request("https://tavfiqnashr.uz/api/admin/posts"),
    { ...env, GITHUB_TOKEN: "" });
  assert.equal(r.status, 500);
});

console.log(`\n${pass} checks passed`);
