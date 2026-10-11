/**
 * TAVFIQNASHR books admin API.
 *
 * Serves only /api/admin/* . The public site stays static on GitHub Pages;
 * this Worker exists because a static host cannot check a password or hold a
 * GitHub token. The token never reaches the browser.
 *
 * Auth: username + PBKDF2-SHA256 password hash, both Worker secrets. On success
 * the Worker sets an HttpOnly, Secure, SameSite=Strict cookie holding an
 * HMAC-signed session token. Write endpoints additionally require the
 * X-Requested-With header, which a cross-site form post cannot set.
 */

const COOKIE = "tn_admin";
const LANGS = new Set(["uz", "ru"]);
const SLUG_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const MAX_BODY = 200 * 1024;
const MAX_IMAGE = 2 * 1024 * 1024;        // decoded cover size
const IMAGE_EXT = { jpg: "jpg", jpeg: "jpg", png: "png", webp: "webp" };

const enc = new TextEncoder();
const dec = new TextDecoder();

// ------------------------------------------------------------------ helpers
const json = (data, status = 200, headers = {}) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", ...headers },
  });

const b64 = {
  enc: (bytes) => btoa(String.fromCharCode(...new Uint8Array(bytes))),
  dec: (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0)),
  url: (bytes) => b64.enc(bytes).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, ""),
  unurl: (s) => b64.dec(s.replace(/-/g, "+").replace(/_/g, "/")),
};

/** Length-independent comparison, so timing does not leak the secret. */
function timingSafeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

async function hmac(secret, data) {
  const key = await crypto.subtle.importKey(
    "raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(data)));
}

/** Verify `pbkdf2$<iterations>$<salt_b64>$<hash_b64>` as produced by tools/hash-password.py */
async function verifyPassword(password, stored) {
  const parts = String(stored || "").split("$");
  if (parts.length !== 4 || parts[0] !== "pbkdf2") return false;
  const iterations = Number(parts[1]);
  // Workers' WebCrypto refuses PBKDF2 above 100k iterations, and deriveBits
  // throws rather than returning false — catch it here so a mis-generated hash
  // is a clear log line, not an opaque 500.
  if (!Number.isInteger(iterations) || iterations < 1000) return false;
  if (iterations > 100000) {
    console.error(`ADMIN_PASSWORD_HASH uses ${iterations} iterations; Workers allows at most 100000. Regenerate it with tools/gen-admin-password.py`);
    return false;
  }
  let salt, expected;
  try {
    salt = b64.dec(parts[2]);
    expected = b64.dec(parts[3]);
  } catch {
    return false;
  }
  const key = await crypto.subtle.importKey(
    "raw", enc.encode(password), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", salt, iterations, hash: "SHA-256" }, key, expected.length * 8);
  return timingSafeEqual(new Uint8Array(bits), expected);
}

async function issueSession(env, username) {
  const hours = Number(env.SESSION_HOURS || 8);
  const payload = { sub: username, exp: Math.floor(Date.now() / 1000) + hours * 3600 };
  const body = b64.url(enc.encode(JSON.stringify(payload)));
  const sig = b64.url(await hmac(env.SESSION_SECRET, body));
  return { token: `v1.${body}.${sig}`, maxAge: hours * 3600 };
}

async function readSession(env, request) {
  const raw = (request.headers.get("cookie") || "")
    .split(";").map((c) => c.trim())
    .find((c) => c.startsWith(COOKIE + "="));
  if (!raw) return null;
  const [v, body, sig] = raw.slice(COOKIE.length + 1).split(".");
  if (v !== "v1" || !body || !sig) return null;
  let expect;
  try {
    expect = b64.url(await hmac(env.SESSION_SECRET, body));
  } catch {
    return null;
  }
  if (!timingSafeEqual(enc.encode(sig), enc.encode(expect))) return null;
  let payload;
  try {
    payload = JSON.parse(dec.decode(b64.unurl(body)));
  } catch {
    return null;
  }
  if (!payload.exp || payload.exp < Math.floor(Date.now() / 1000)) return null;
  return payload;
}

const cookieHeader = (token, maxAge) =>
  `${COOKIE}=${token}; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=${maxAge}`;

// ------------------------------------------------------------------- GitHub
async function gh(env, path, init = {}) {
  const res = await fetch(`https://api.github.com${path}`, {
    ...init,
    headers: {
      authorization: `Bearer ${env.GITHUB_TOKEN}`,
      accept: "application/vnd.github+json",
      "user-agent": "tavfiqnashr-admin",
      "x-github-api-version": "2022-11-28",
      ...(init.body ? { "content-type": "application/json" } : {}),
      ...(init.headers || {}),
    },
  });
  return res;
}

const contentPath = (lang, slug) => `content/books/${lang}/${slug}.md`;
const coverPath = (name) => `assets/img/books/${name}`;

async function getFile(env, path) {
  const res = await gh(env, `/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/contents/${path}?ref=${env.GITHUB_BRANCH}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`github get ${path}: ${res.status}`);
  const data = await res.json();
  return { sha: data.sha, text: dec.decode(b64.dec(data.content.replace(/\n/g, ""))) };
}

/** Sha only — never decodes the body, so it is safe for binary covers (and
 *  for files over 1MB, where the Contents API omits inline content). */
async function getSha(env, path) {
  const res = await gh(env, `/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/contents/${path}?ref=${env.GITHUB_BRANCH}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`github head ${path}: ${res.status}`);
  return (await res.json()).sha;
}

async function putFile(env, path, text, message, sha) {
  const res = await gh(env, `/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/contents/${path}`, {
    method: "PUT",
    body: JSON.stringify({
      message,
      content: b64.enc(enc.encode(text)),
      branch: env.GITHUB_BRANCH,
      ...(sha ? { sha } : {}),
    }),
  });
  if (!res.ok) throw new Error(`github put ${path}: ${res.status} ${await res.text()}`);
  return res.json();
}

// ------------------------------------------------------------- front matter
const FIELDS = ["title", "author", "date", "description", "image",
                "price", "pages", "cover", "language", "tag", "quote", "featured"];

function buildMarkdown(p) {
  const lines = [];
  for (const f of FIELDS) {
    const v = (p[f] ?? "").toString().trim();
    if (v) lines.push(`${f}: ${v}`);
  }
  const body = String(p.body || "").replace(/\r\n/g, "\n").trim();
  return lines.join("\n") + "\n\n" + body + "\n";
}

function parseMarkdown(text) {
  const i = text.indexOf("\n\n");
  const head = i === -1 ? text : text.slice(0, i);
  const body = i === -1 ? "" : text.slice(i + 2);
  const meta = {};
  for (const line of head.split("\n")) {
    const k = line.indexOf(":");
    if (k > 0) meta[line.slice(0, k).trim()] = line.slice(k + 1).trim();
  }
  return { ...meta, body };
}

function validate(p) {
  const errs = [];
  if (!p.title || p.title.length > 200) errs.push("title is required (max 200 characters)");
  if (!p.author || p.author.length > 200) errs.push("author is required (max 200 characters)");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(p.date || "")) errs.push("date must be YYYY-MM-DD");
  if (!p.description || p.description.length > 400) errs.push("description is required (max 400 characters)");
  if (!p.image) errs.push("a cover image is required");
  if (p.image && !/^[a-z0-9][a-z0-9._-]*\.(jpg|png|webp)$/i.test(p.image)) {
    errs.push("image must be a plain file name ending in .jpg, .png or .webp");
  }
  // Front matter is one key per line, so a newline in any of these would
  // silently corrupt the file the generator reads back.
  for (const f of FIELDS) {
    if (p[f] && /[\r\n]/.test(p[f])) errs.push(`${f} must be a single line`);
  }
  return errs;
}

// -------------------------------------------------------------------- routes
async function handle(request, env) {
  const url = new URL(request.url);
  const path = url.pathname.replace(/^\/api\/admin/, "") || "/";

  for (const k of ["ADMIN_USERNAME", "ADMIN_PASSWORD_HASH", "SESSION_SECRET", "GITHUB_TOKEN"]) {
    if (!env[k]) return json({ error: `Worker is missing the ${k} secret` }, 500);
  }

  if (path === "/login" && request.method === "POST") {
    let creds;
    try {
      creds = await request.json();
    } catch {
      return json({ error: "Invalid request" }, 400);
    }
    const userOk = timingSafeEqual(enc.encode(String(creds.username || "")), enc.encode(env.ADMIN_USERNAME));
    const passOk = await verifyPassword(String(creds.password || ""), env.ADMIN_PASSWORD_HASH);
    if (!userOk || !passOk) {
      // Slow down guessing a little; pair with a Cloudflare rate-limit rule.
      await new Promise((r) => setTimeout(r, 700));
      return json({ error: "Login yoki parol noto‘g‘ri" }, 401);
    }
    const { token, maxAge } = await issueSession(env, env.ADMIN_USERNAME);
    return json({ ok: true, user: env.ADMIN_USERNAME }, 200, { "set-cookie": cookieHeader(token, maxAge) });
  }

  if (path === "/logout" && request.method === "POST") {
    return json({ ok: true }, 200, { "set-cookie": `${COOKIE}=; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=0` });
  }

  const session = await readSession(env, request);
  if (!session) return json({ error: "unauthorized" }, 401);

  if (path === "/session") return json({ ok: true, user: session.sub, exp: session.exp });

  // Any state change must carry this header — a cross-site form cannot set it.
  if (request.method !== "GET" && request.headers.get("x-requested-with") !== "tn-admin") {
    return json({ error: "missing X-Requested-With" }, 403);
  }

  // Returns enough of each book to render a readable list — a bare slug tells
  // the publisher nothing about which book it is.
  if (path === "/books" && request.method === "GET") {
    const out = {};
    for (const lang of LANGS) {
      const res = await gh(env, `/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/contents/content/books/${lang}?ref=${env.GITHUB_BRANCH}`);
      if (!res.ok) { out[lang] = []; continue; }
      const slugs = (await res.json())
        .filter((f) => f.name.endsWith(".md"))
        .map((f) => f.name.slice(0, -3))
        .slice(0, 60);                      // keep well inside the subrequest budget
      const entries = await Promise.all(slugs.map(async (slug) => {
        try {
          const file = await getFile(env, contentPath(lang, slug));
          const m = file ? parseMarkdown(file.text) : {};
          return { slug, title: m.title || slug, image: m.image || "",
                   date: m.date || "", featured: m.featured || "" };
        } catch {
          return { slug, title: slug, image: "", date: "", featured: "" };
        }
      }));
      entries.sort((a, b) => (b.date || "").localeCompare(a.date || ""));
      out[lang] = entries;
    }
    return json(out);
  }

  // Cover upload: the browser sends base64 so the binary never has to be
  // multipart-parsed in the Worker; the token stays server-side either way.
  if (path === "/media" && request.method === "POST") {
    let payload;
    try {
      payload = await request.json();
    } catch {
      return json({ error: "Invalid request" }, 400);
    }
    const ext = IMAGE_EXT[String(payload.ext || "").toLowerCase().replace(/^\./, "")];
    if (!ext) return json({ error: "Only .jpg, .png or .webp covers are allowed" }, 400);
    const base = String(payload.name || "cover").toLowerCase()
      .replace(/\.[a-z0-9]+$/, "").replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "").slice(0, 60) || "cover";
    const data = String(payload.data || "");
    if (!/^[A-Za-z0-9+/=]+$/.test(data)) return json({ error: "Invalid image data" }, 400);
    if (data.length * 0.75 > MAX_IMAGE) {
      return json({ error: "Rasm hajmi 2 MB dan oshmasin" }, 413);
    }
    const filename = `${base}.${ext}`;
    const existingSha = await getSha(env, coverPath(filename));
    const res = await gh(env, `/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/contents/${coverPath(filename)}`, {
      method: "PUT",
      body: JSON.stringify({
        message: `${existingSha ? "Replace" : "Add"} book cover: ${filename}`,
        content: data, branch: env.GITHUB_BRANCH,
        ...(existingSha ? { sha: existingSha } : {}),
      }),
    });
    if (!res.ok) throw new Error(`github cover upload: ${res.status}`);
    return json({ ok: true, image: filename });
  }

  const m = path.match(/^\/books\/(uz|ru)\/([^/]+)$/);
  if (m) {
    const [, lang, slug] = m;
    if (!SLUG_RE.test(slug)) return json({ error: "Invalid slug" }, 400);
    const file = contentPath(lang, slug);

    if (request.method === "GET") {
      const existing = await getFile(env, file);
      if (!existing) return json({ error: "not found" }, 404);
      return json({ slug, lang, ...parseMarkdown(existing.text) });
    }

    if (request.method === "PUT") {
      const raw = await request.text();
      if (raw.length > MAX_BODY) return json({ error: "Entry is too large" }, 413);
      let post;
      try {
        post = JSON.parse(raw);
      } catch {
        return json({ error: "Invalid request" }, 400);
      }
      const errs = validate(post);
      if (errs.length) return json({ error: errs.join("; ") }, 400);
      const existing = await getFile(env, file);
      await putFile(env, file, buildMarkdown(post),
        `${existing ? "Update" : "Add"} ${lang} book: ${slug}`, existing?.sha);
      return json({ ok: true, created: !existing });
    }

    if (request.method === "DELETE") {
      const existing = await getFile(env, file);
      if (!existing) return json({ error: "not found" }, 404);
      const res = await gh(env, `/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/contents/${file}`, {
        method: "DELETE",
        body: JSON.stringify({ message: `Delete ${lang} book: ${slug}`, sha: existing.sha, branch: env.GITHUB_BRANCH }),
      });
      if (!res.ok) throw new Error(`github delete: ${res.status}`);
      return json({ ok: true });
    }
  }

  return json({ error: "not found" }, 404);
}

export default {
  async fetch(request, env) {
    if (new URL(request.url).protocol !== "https:") return json({ error: "https required" }, 400);
    try {
      return await handle(request, env);
    } catch (err) {
      // Never surface the GitHub token or raw upstream errors to the browser.
      console.error(err?.stack || String(err));
      return json({ error: "Server xatosi. Keyinroq urinib ko‘ring." }, 500);
    }
  },
};
