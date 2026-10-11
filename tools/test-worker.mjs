/** Exercises worker/src/worker.js against a mocked GitHub API. Run: node tools/test-worker.mjs */
import assert from "node:assert/strict";
import cryptoNode from "node:crypto";

const PASSWORD = "a-very-long-test-password";
const ITER = 100000;  // must stay within the Workers cap
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
  ["content/books/uz/komil-inson.md",
    "title: Komil inson\nauthor: Aziziddin Nasafiy\ndate: 2026-08-15\ndescription: Tasavvuf namunasi.\nimage: komil-inson.jpg\n\nMatn boshlanadi.\n"],
]);
const calls = [];
globalThis.fetch = async (url, init = {}) => {
  const u = new URL(url);
  calls.push({ url: u.pathname, method: init.method || "GET", auth: init.headers?.authorization,
    body: init.body ? JSON.parse(init.body) : null });
  const m = u.pathname.match(/\/repos\/[^/]+\/[^/]+\/contents\/(.+)$/);
  const path = m ? decodeURIComponent(m[1]) : "";
  const ok = (body) => new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });

  if (path.startsWith("content/books/") && !path.endsWith(".md")) {
    const lang = path.split("/")[2];
    return ok([...files.keys()].filter((f) => f.startsWith(`content/books/${lang}/`))
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
  assert.equal((await call("/books")).status, 401);
});

await t("rejects a forged session signature", async () => {
  const bad = cookie.replace(/.$/, (c) => (c === "A" ? "B" : "A"));
  assert.equal((await call("/books", { headers: { cookie: bad } })).status, 401);
});

await t("rejects an expired session", async () => {
  const short = { ...env, SESSION_HOURS: "-1" };
  const r = await worker.fetch(new Request("https://tavfiqnashr.uz/api/admin/login",
    { method: "POST", body: JSON.stringify({ username: "nashriyot", password: PASSWORD }) }), short);
  const expired = r.headers.get("set-cookie").split(";")[0];
  assert.equal((await worker.fetch(new Request("https://tavfiqnashr.uz/api/admin/books",
    { headers: { cookie: expired } }), short)).status, 401);
});

await t("blocks writes without the CSRF header", async () => {
  const r = await call("/books/uz/x-post", {
    method: "PUT", headers: { cookie },
    body: JSON.stringify({ title: "T", author: "A", date: "2026-01-01", description: "D", image: "c.jpg", body: "B" }),
  });
  assert.equal(r.status, 403);
});

// ---- content ---------------------------------------------------------------
await t("lists books per language", async () => {
  const d = await (await call("/books", { headers: { cookie } })).json();
  assert.deepEqual(d.uz, ["komil-inson"]);
  assert.deepEqual(d.ru, []);
});

await t("reads an existing book and splits front matter from body", async () => {
  const d = await (await call("/books/uz/komil-inson", { headers: { cookie } })).json();
  assert.equal(d.title, "Komil inson");
  assert.equal(d.author, "Aziziddin Nasafiy");
  assert.equal(d.image, "komil-inson.jpg");
  assert.equal(d.body.trim(), "Matn boshlanadi.");
});

await t("rejects a bad slug", async () => {
  const r = await post("/books/uz/Bad_Slug", { title: "T", author: "A", date: "2026-01-01", description: "D", image: "c.jpg", body: "B" }, { cookie });
  assert.equal(r.status, 400);
});

await t("rejects invalid front-matter values", async () => {
  for (const bad of [
    { title: "", author: "A", date: "2026-01-01", description: "D", image: "c.jpg" },
    { title: "T", author: "", date: "2026-01-01", description: "D", image: "c.jpg" },
    { title: "T", author: "A", date: "01-01-2026", description: "D", image: "c.jpg" },
    { title: "T", author: "A", date: "2026-01-01", description: "D", image: "" },
    { title: "T", author: "A", date: "2026-01-01", description: "D", image: "../escape.jpg" },
    { title: "Two\nlines", author: "A", date: "2026-01-01", description: "D", image: "c.jpg" },
  ]) {
    const r = await post("/books/uz/some-slug", bad, { cookie });
    assert.equal(r.status, 400, JSON.stringify(bad));
  }
});

await t("creates a book with correct front matter", async () => {
  calls.length = 0;
  const r = await post("/books/ru/novaya-kniga", {
    title: "Новая книга", author: "Автор", date: "2026-10-11", description: "Описание.",
    image: "novaya-kniga.jpg", pages: "120 стр.", featured: "yes",
    body: "## Заголовок\n\nТекст.",
  }, { cookie });
  assert.equal(r.status, 200);
  const md = files.get("content/books/ru/novaya-kniga.md");
  assert.equal(md.split("\n\n")[0],
    "title: Новая книга\nauthor: Автор\ndate: 2026-10-11\ndescription: Описание.\n" +
    "image: novaya-kniga.jpg\npages: 120 стр.\nfeatured: yes");
  assert.match(md, /## Заголовок/);
  const created = calls.filter((c) => c.method === "PUT").pop();
  assert.equal("sha" in created.body, false, "a new file must not send a sha");
});

await t("updates an existing book using its sha", async () => {
  calls.length = 0;
  const r = await post("/books/uz/komil-inson", {
    title: "Komil inson (yangilandi)", author: "Aziziddin Nasafiy", date: "2026-08-15",
    description: "D", image: "komil-inson.jpg", body: "Yangi matn.",
  }, { cookie });
  assert.equal(r.status, 200);
  const put = calls.find((c) => c.method === "PUT");
  assert.ok(put, "expected a PUT to GitHub");
  assert.equal(put.body.sha, "sha-content/books/uz/komil-inson.md",
    "an update must send the existing file sha or GitHub rejects it");
  assert.equal(put.body.branch, "main");
  assert.match(files.get("content/books/uz/komil-inson.md"), /yangilandi/);
});

await t("deletes a book", async () => {
  const r = await call("/books/ru/novaya-kniga", { method: "DELETE", headers: { cookie, "x-requested-with": "tn-admin" } });
  assert.equal(r.status, 200);
  assert.equal(files.has("content/books/ru/novaya-kniga.md"), false);
});

// ---- cover upload ----------------------------------------------------------
await t("uploads a cover and returns a safe file name", async () => {
  const png = Buffer.from("fake-png-bytes").toString("base64");
  const r = await call("/media", {
    method: "POST", headers: { cookie, "x-requested-with": "tn-admin" },
    body: JSON.stringify({ name: "Yangi Kitob! (2026)", ext: "JPEG", data: png }),
  });
  assert.equal(r.status, 200);
  const d = await r.json();
  assert.equal(d.image, "yangi-kitob-2026.jpg", "name must be slugified and the ext normalised");
  assert.ok(files.has("assets/img/books/yangi-kitob-2026.jpg"));
});

await t("rejects a non-image extension", async () => {
  const r = await call("/media", {
    method: "POST", headers: { cookie, "x-requested-with": "tn-admin" },
    body: JSON.stringify({ name: "x", ext: "svg", data: "AAAA" }),
  });
  assert.equal(r.status, 400);
});

await t("rejects an oversized cover", async () => {
  const r = await call("/media", {
    method: "POST", headers: { cookie, "x-requested-with": "tn-admin" },
    body: JSON.stringify({ name: "big", ext: "jpg", data: "A".repeat(3 * 1024 * 1024) }),
  });
  assert.equal(r.status, 413);
});

await t("cover upload needs the CSRF header", async () => {
  const r = await call("/media", {
    method: "POST", headers: { cookie },
    body: JSON.stringify({ name: "x", ext: "jpg", data: "AAAA" }),
  });
  assert.equal(r.status, 403);
});

// ---- secrets ---------------------------------------------------------------
await t("never returns the GitHub token to the browser", async () => {
  for (const p of ["/books", "/books/uz/komil-inson", "/session"]) {
    const body = await (await call(p, { headers: { cookie } })).text();
    assert.equal(body.includes(env.GITHUB_TOKEN), false, p);
  }
  assert.ok(calls.every((c) => !c.auth || c.auth === `Bearer ${env.GITHUB_TOKEN}`));
});

await t("fails closed when a secret is missing", async () => {
  const r = await worker.fetch(new Request("https://tavfiqnashr.uz/api/admin/books"),
    { ...env, GITHUB_TOKEN: "" });
  assert.equal(r.status, 500);
});

// ---- platform limits ------------------------------------------------------
// Workers' WebCrypto rejects PBKDF2 above 100k iterations while Node and
// Python accept far more, so a hash that works locally can still 500 in
// production. Pin both generators to the ceiling.
await t("both password generators stay within the Workers PBKDF2 cap", async () => {
  const fs = await import("node:fs");
  for (const f of ["tools/hash-password.py", "tools/gen-admin-password.py"]) {
    const src = fs.readFileSync(new URL("../" + f, import.meta.url), "utf8");
    const m = src.match(/ITERATIONS = ([\d_]+)/);
    assert.ok(m, `${f}: ITERATIONS not found`);
    const iters = Number(m[1].replace(/_/g, ""));
    assert.ok(iters <= 100000, `${f}: ${iters} iterations exceeds the Workers limit of 100000`);
    assert.ok(iters >= 100000, `${f}: ${iters} iterations is below the ceiling we can afford`);
  }
});

await t("rejects a hash whose iteration count Workers cannot run", async () => {
  const tooMany = { ...env, ADMIN_PASSWORD_HASH: env.ADMIN_PASSWORD_HASH.replace(/^pbkdf2\$\d+/, "pbkdf2$210000") };
  const r = await worker.fetch(new Request("https://tavfiqnashr.uz/api/admin/login",
    { method: "POST", body: JSON.stringify({ username: "nashriyot", password: PASSWORD }) }), tooMany);
  assert.equal(r.status, 401, "must fail closed as a login failure, not a 500");
});

console.log(`\n${pass} checks passed`);
