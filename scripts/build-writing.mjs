#!/usr/bin/env node
// Build /writing from markdown. Zero config beyond writing/topics.json + posts/*.md.
//   node scripts/build-writing.mjs --out _site
// Outputs: writing/index.html, writing/<topic>/index.html, writing/<topic>/<slug>/index.html,
//          writing/feed.xml, and injects latest posts into <out>/index.html at <!-- WRITING:LATEST -->.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { marked } from "marked";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const outArg = process.argv.indexOf("--out");
const OUT = path.resolve(outArg > -1 ? process.argv[outArg + 1] : "_site");
const SRC = path.join(ROOT, "writing");
const SITE = "https://rayvelabs.com";

const layout = fs.readFileSync(path.join(SRC, "_layout.html"), "utf8");
const topics = JSON.parse(fs.readFileSync(path.join(SRC, "topics.json"), "utf8")).topics;
const topicBySlug = Object.fromEntries(topics.map(t => [t.slug, t]));

// ---------- frontmatter ----------
function parseFrontmatter(raw) {
  const m = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  if (!m) return [{}, raw];
  const fm = {};
  for (const line of m[1].split(/\r?\n/)) {
    const i = line.indexOf(":"); if (i < 1) continue;
    const k = line.slice(0, i).trim(); let v = line.slice(i + 1).trim();
    if (v.startsWith("[") && v.endsWith("]")) v = v.slice(1, -1).split(",").map(s => s.trim()).filter(Boolean);
    else if (v === "true") v = true; else if (v === "false") v = false;
    else v = v.replace(/^["']|["']$/g, "");
    fm[k] = v;
  }
  return [fm, m[2]];
}
const esc = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const fmtDate = d => new Date(d + "T00:00:00Z").toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
const readMin = md => Math.max(1, Math.round(md.split(/\s+/).length / 220));
const page = ({ title, desc, body, urlPath }) =>
  layout.replace("{{TITLE}}", esc(title)).replace("{{DESC}}", esc(desc)).replace("{{PATH}}", urlPath).replace("{{BODY}}", body);
const write = (rel, html) => { const p = path.join(OUT, rel); fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, html); };

// ---------- load posts ----------
const posts = [];
for (const f of fs.readdirSync(path.join(SRC, "posts")).filter(f => f.endsWith(".md")).sort()) {
  const raw = fs.readFileSync(path.join(SRC, "posts", f), "utf8");
  const [fm, md] = parseFrontmatter(raw);
  if (fm.draft === true) continue;
  const slug = f.replace(/\.md$/, "").replace(/^\d{4}-\d{2}-\d{2}-/, "");
  const date = fm.date || (f.match(/^(\d{4}-\d{2}-\d{2})/) || [])[1];
  if (!fm.title || !date) { console.error(`! skipping ${f}: needs title + date`); continue; }
  if (!topicBySlug[fm.topic]) { console.error(`! skipping ${f}: unknown topic "${fm.topic}" (add it to writing/topics.json)`); continue; }
  posts.push({ slug, date, title: fm.title, summary: fm.summary || "", tags: fm.tags || [], topic: fm.topic,
               html: marked.parse(md), minutes: readMin(md), url: `/writing/${fm.topic}/${slug}/` });
}
posts.sort((a, b) => (a.date < b.date ? 1 : -1));
console.log(`writing: ${posts.length} post(s) across ${new Set(posts.map(p => p.topic)).size} topic(s)`);

// ---------- post pages ----------
const li = p => `<li><span class="t"><a href="${p.url}">${esc(p.title)}</a></span><span class="d">${fmtDate(p.date)}</span>${p.summary ? `<p class="s">${esc(p.summary)}</p>` : ""}</li>`;
for (const p of posts) {
  const t = topicBySlug[p.topic];
  const body = `<div class="kicker"><a href="/writing/${t.slug}/">${esc(t.name)}</a></div>
<h1>${esc(p.title)}</h1>
${p.summary ? `<p class="lede">${esc(p.summary)}</p>` : ""}
<div class="meta"><span>${fmtDate(p.date)}</span><span>${p.minutes} min read</span>${p.tags.map(x => `<span class="chip">${esc(x)}</span>`).join("")}</div>
<article class="prose">${p.html}</article>`;
  write(`writing/${t.slug}/${p.slug}/index.html`, page({ title: p.title, desc: p.summary || p.title, body, urlPath: p.url }));
}

// ---------- topic pages ----------
for (const t of topics) {
  const tp = posts.filter(p => p.topic === t.slug);
  // Always emit a topic page so homepage/topic links never 404; empty topics say so honestly.
  const list = tp.length
    ? `<div class="meta"><span>${tp.length} ${tp.length === 1 ? "post" : "posts"}</span></div><ul class="post-list">${tp.map(li).join("")}</ul>`
    : `<div class="meta"><span>first piece in progress</span><a href="/writing/feed.xml">subscribe via RSS</a></div><p class="lede" style="color:var(--faint)">Nothing published here yet. <a href="/writing/">See what's live →</a></p>`;
  const body = `<div class="kicker"><a href="/writing/">Writing</a></div><h1>${esc(t.name)}</h1><p class="lede">${esc(t.blurb)}</p>${list}`;
  write(`writing/${t.slug}/index.html`, page({ title: t.name, desc: t.blurb, body, urlPath: `/writing/${t.slug}/` }));
}

// ---------- writing index (by topic) ----------
{
  const sections = topics.map(t => {
    const tp = posts.filter(p => p.topic === t.slug);
    if (!tp.length) return "";
    return `<section class="topic"><h2><a href="/writing/${t.slug}/">${esc(t.name)}</a></h2><p class="blurb">${esc(t.blurb)}</p><ul class="post-list">${tp.slice(0, 6).map(li).join("")}</ul></section>`;
  }).join("");
  const body = `<div class="kicker">Writing</div><h1>Small, finished thoughts.</h1>
<p class="lede">Short pieces on discovery, generative AI, cryptography, compliance, and the research behind the labs — organized by topic.</p>
<div class="meta"><span>${posts.length} ${posts.length === 1 ? "post" : "posts"}</span><a href="/writing/feed.xml">RSS</a></div>${sections}`;
  write("writing/index.html", page({ title: "Writing", desc: "Short pieces on security research, by topic.", body, urlPath: "/writing/" }));
}

// ---------- RSS ----------
{
  const items = posts.slice(0, 20).map(p => `<item><title>${esc(p.title)}</title><link>${SITE}${p.url}</link><guid>${SITE}${p.url}</guid><pubDate>${new Date(p.date + "T00:00:00Z").toUTCString()}</pubDate><category>${esc(topicBySlug[p.topic].name)}</category><description>${esc(p.summary)}</description></item>`).join("");
  write("writing/feed.xml", `<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>RayveLabs — Writing</title><link>${SITE}/writing/</link><description>Short pieces on security research, by topic.</description>${items}</channel></rss>`);
}

// ---------- homepage "latest" strip ----------
{
  const idx = path.join(OUT, "index.html");
  if (fs.existsSync(idx)) {
    let html = fs.readFileSync(idx, "utf8");
    const latest = posts.slice(0, 3).map(p => `<li><span class="t"><a href="${p.url}">${esc(p.title)}</a></span><span class="d">${fmtDate(p.date)} · ${esc(topicBySlug[p.topic].name)}</span>${p.summary ? `<p class="s">${esc(p.summary)}</p>` : ""}</li>`).join("");
    const block = `<!-- WRITING:LATEST --><ul class="post-list w-latest">${latest}</ul><!-- /WRITING:LATEST -->`;
    const re = /<!-- WRITING:LATEST -->[\s\S]*?<!-- \/WRITING:LATEST -->/;
    if (re.test(html)) { fs.writeFileSync(idx, html.replace(re, block)); console.log("homepage: latest-writing strip injected"); }
  }
}
console.log(`writing: built into ${OUT}`);
