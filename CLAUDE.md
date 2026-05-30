# RayveLabs · Project Briefing for Claude Code

This is the operational briefing for **rayvelabs.com**. Any agent (Claude Code,
cursor, or human) picking up work on this repo should read this first.

---

## What this is

A small open-research cybersecurity teaching site at **https://rayvelabs.com**.
The site is the property of **Rayve Malhotra** — student of SEAS-8414
*Analytical Tools for Cyber* at The George Washington University, taught by
**Dr. Ravinder Mallarapu**.

The site hosts interactive labs ("RayveNet") that walk students through
Dr. Mallarapu's chapters with hands-on tools, games, capstones, and
discipline checklists.

---

## Repo + hosting

| Layer | Where |
|---|---|
| **Source repo** | https://github.com/rayvemalhotra/rayvelabs (public) |
| **Local clone** | `/Users/malhotra/Desktop/GW/Third Semester/Rayve Project/rebuild` |
| **Hosting** | GitHub Pages, custom domain `rayvelabs.com` |
| **DNS** | Squarespace |
| **Deploy** | GitHub Actions workflow (`.github/workflows/deploy.yml`) builds + minifies + deploys via `actions/deploy-pages@v4`. Post-build node syntax check gates every deploy. |
| **Uptime** | `.github/workflows/uptime.yml` pings the site every 15 min, opens a labeled issue on failure |

**Source of truth for what's actually deployed**: read `OPERATIONS.md` in this
directory. It documents DNS records, Pages config, the critical
"repo must stay public" invariant, and the recovery runbook.

---

## Stack

Single-page static site, no framework. Two HTML files do the work:

| File | Purpose |
|---|---|
| `index.html` | Homepage · parallax hero with portrait, animated loader, projects card linking to RayveNet |
| `rayvenet.html` | The RayveNet labs — 5 tabs (Network Discovery, Cascade Lab, Threat Hunt, Fingerprinting, Key terms). The interactive teaching tool. |
| `LICENSE` | All Rights Reserved with explicit academic-context clause |
| `SECURITY.md` | Responsible-disclosure policy |
| `OPERATIONS.md` | DNS records, Pages settings, recovery runbook |
| `robots.txt` | Allows search engines, blocks AI training crawlers (GPTBot, ChatGPT-User, anthropic-ai, Claude-Web, CCBot, PerplexityBot, Bytespider, Google-Extended) |
| `.nojekyll` | Disables Jekyll on GitHub Pages |
| `CNAME` | Contains `rayvelabs.com` |
| `rayve.jpg` | Hero portrait |
| `.gitignore` | Standard ignores (`.DS_Store`, `.claude/`, `.env`, etc.) |

---

## The chapter structure (rayvenet.html)

Each chapter is a `<div class="pane">` with `data-pane` matching its tab's
`data-pane` attribute. The tab nav switches `.on` class.

### Five tabs

1. `discovery` — **Chapter 1 · Network Discovery & Asset Inventory**
2. `sim2` — **Chapter 2 · Service Enrichment & Device Fingerprinting** (Cascade Lab)
3. `threat` — **Chapter 3 · Vulnerability Assessment & The Detective Layer** (Threat Hunt)
4. `weblog` — Lab 02 · Web Request Fingerprinting (separate topic)
5. `terms` — Key Terms glossary

### Within each chapter

- A `<header class="nd-chapter-header">` — currently displays only the title; kicker, credit, lede, and question cards are CSS-hidden (they duplicated section content)
- A sticky `<nav class="nd-subnav">` with section links (auto-hides on scroll-down)
- Numbered `<section class="nd-section" id="...">` blocks
- A capstone game / lab at the end
- A "Sources & Further Reading" panel
- A "Discipline Checklist" with click-to-tick rows
- A `<div class="nd-chapter-foot">` with Dr. Mallarapu attribution
- A `<script>` IIFE that wires up all the chapter's interactivity

### CSS naming conventions

- `.nd-*` — shared chapter shell (header, sub-nav, section, prose, card, btn, runcase, reveal, checklist, handoff)
- `.c2-*` — Chapter 2 (Cascade Lab) specific elements
- `.t3-*` — Chapter 3 (Threat Hunt) specific elements
- `.rl-*` — Student layer (glossary terms, cross-chapter jumps, quizzes, progress)
- `.wl-*` — Web Log Lab specific elements

### JS conventions

- Each chapter wraps its logic in a top-level IIFE
- Element IDs are prefixed by chapter: `nd*` (Ch.1), `c2*` (Ch.2), `t3*` (Ch.3)
- A single shared "student layer" IIFE at the very bottom of `<body>` handles glossary tooltips, cross-chapter jumps, quizzes, and localStorage progress tracking
- `localStorage` keys are namespaced: `rl_progress_v1`, `rl_kev_v1`, `rl_nvd_cache_v1`, `rl_epss_cache_v1`, `rl_soc_best_v1`, `rl_roul_best_v1`

### Live data sources (Chapter 3)

| API | Endpoint | Notes |
|---|---|---|
| **CISA KEV** | `https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json` | Free · no auth · CORS OK · cached 24h |
| **NVD CVE search** | `https://services.nvd.nist.gov/rest/json/cves/2.0` | Free · no auth · 5 req/30s without API key, 50 req/30s with · CORS OK · cached 24h per CPE |
| **FIRST EPSS** | `https://api.first.org/data/v1/epss?cve=CVE-X,CVE-Y,...` | Free · no auth · batched · CORS OK · cached 24h per CVE |

All three are called client-side. No server logic. No secrets in the repo.

---

## Build pipeline — IMPORTANT

`.github/workflows/deploy.yml` runs on every push to `main`:

1. Checkout
2. `npm install -g html-minifier-terser terser`
3. `rsync` everything to `_site/` (excluding `.git`, `.github`, `OPERATIONS.md`, etc.)
4. Minify every `*.html` in `_site/` with aggressive flags:
   - HTML: collapse whitespace, remove comments, conservative collapse
   - CSS: minified
   - JS: **mangled** with `quote_style: 1` (force single-quoted output)
5. **POST-BUILD CHECK** (added after a critical bug — see below): a `node` script that parses every `<script>` block in every minified HTML and fails the deploy if any throws a `SyntaxError`
6. Upload to GitHub Pages, deploy

### The minifier bug we MUST NOT recreate

**Symptom**: page rendered fine, no interactivity, console showed
`TypeError: Cannot read properties of null (reading 'addEventListener')`.

**Root cause**: my source had a JS string like
`'<?xml version="1.0"?>'` (single-quoted, with embedded double quotes).
Terser's minifier rewrote the outer quotes to double quotes but **failed to
escape the inner double quotes** — producing invalid JS:
`"<?xml version="1.0"?>"`. The minified IIFE failed to parse, so nothing in
the chapter's script ran.

**Defenses now in place**:
1. `quote_style: 1` in Terser config — forces single-quoted output, which
   correctly escapes inner single quotes
2. Post-build `node --check` runs against every minified script block
3. Convention: **when writing JS strings that contain quotes, use the
   opposite outer quote type or escape explicitly** (`"<?xml version=\"1.0\"?>"`)

If you change `deploy.yml`, verify the post-build check still runs.

---

## License context

**LICENSE is All Rights Reserved.** Specifically:

- Source is public on GitHub so students and visitors can read it.
- Copying, redistributing, or **submitting any portion as your own work
  in academic, employment, or commercial contexts** is expressly prohibited.
- The CC-BY license earlier in the project was replaced when context shifted
  to academic-plagiarism prevention.
- The deploy pipeline obfuscates (mangles JS, minifies HTML) the production
  build to make casual copy-paste harder — but this is a speed bump, not a
  legal substitute.

**When asked to change the license**: confirm intent. Don't loosen without
explicit user direction.

---

## Current state of work (as of last session)

Three full chapters shipped with the same shape:

- **Ch.1 Network Discovery** — 13 sections + 26-device capstone + discipline checklist
  + 5 hands-on tools (ARP harvester, Router/SNMP, mDNS, SSDP, TCP pilot) +
  evidence-classes table + recall formula + posture grid + counterfactual table
- **Ch.2 Cascade Lab** — 14 sections + 26-device enrichment capstone + discipline +
  13 evidence sources + structural-independence claim builder + 12-adapter fan-out +
  port-driven adapter selection + CPE builder + adversarial flip cards +
  worked traces (Hikvision, Chromecast) + confidence ceilings table
- **Ch.3 Threat Hunt** — 14 sections + Patch Tuesday capstone + discipline +
  live CISA KEV feed + interactive CVSS calculator + 5-method comparison +
  correlation puzzle + **live CPE→CVE pipeline exercise (NVD + EPSS API calls)** +
  3 games (Triage Room, Phantom Hunt, Default Cred Roulette) +
  worked traces + Sources & Further Reading panel

Plus a **student layer** shared across all chapters:

- Inline glossary tooltips on ~60 technical terms (click to pin/unpin)
- Cross-chapter jump links — "Chapter 1" / "Ch.1" auto-wrapped
- 5-question self-test at the end of each chapter
- localStorage progress tracking with sub-nav dots + chapter-level badges

---

## What's NOT done — pending work

If the user asks "what's next?", these are the candidates:

1. **Astro / Cloudflare migration** — `rayvenet.html` is now ~770 KB single-file.
   Moving to Astro on Cloudflare Pages would: (a) make adding new chapters 10x
   faster (markdown files instead of HTML editing), (b) give us real headers
   control (HSTS preload, X-Frame-Options, WAF), (c) give us visitor IPs +
   analytics for free. ~3-4 hours of work. **High leverage** — should be the
   next major project.

2. **Chapter 4 (Attack Path Reasoning)** — Dr. M's Chapter 4 PDF hasn't been
   uploaded yet. When it is, follow the Ch.1/Ch.2/Ch.3 build pattern:
   compact header, sticky sub-nav, sections with interactive tools, a
   capstone, a Ch.3→Ch.4 handoff verification, discipline checklist, sources.

3. **Collaboration / comments section** — sketched but not built. Would
   require Supabase + Resend (email moderation flow). User explicitly
   deferred this to focus on chapters first.

4. **Inline source-code references inside chapter prose** — currently the
   Sources section in Ch.3 lists external links in a panel; we could
   additionally annotate inline mentions in prose with citation-style links.

5. **Per-chapter PDF export** — would help students who want offline study
   material. ~1 hour.

6. **Mobile pass** — chapters work on mobile but the games (Triage Room,
   Phantom Hunt drag-drop, CVSS calculator) are desktop-optimized. No
   targeted mobile review has happened yet.

---

## Working conventions

- **Always read this file at the start of a session.** It's the source of truth.
- **Update `OPERATIONS.md`** when DNS records, Pages settings, or any production
  configuration changes.
- **Never weaken the LICENSE** without explicit user direction.
- **Test JS before pushing**: every push to `main` runs the post-build syntax
  check, but catching errors locally is faster than a 60-second deploy round-trip.
  Quick check: `node --check <path-to-extracted-script.js>`.
- **Never commit `.env`, API keys, or secrets**: the site is client-side only;
  there should be no need.
- **Respect the chapter shape**: when adding sections to existing chapters,
  follow the `nd-section` / sub-nav-link / `id="ch-N"` pattern.
- **Maintain the deploy gate**: the `node --check` step in `deploy.yml` is what
  caught the minifier bug. Don't remove it; do extend it (e.g., HTML validation,
  link checking) if it makes sense.
- **Dr. Mallarapu attribution**: every chapter ends with a small italic credit
  footer. Don't strip it.

---

## Common tasks reference

### Add a section to an existing chapter

1. Find the chapter pane: `<div id="discovery|sim2|threat" class="pane">`
2. Find the right insertion point (between two existing `<section>` blocks
   or before the discipline checklist / sources / credit footer)
3. Add a new `<section id="X-Y" class="nd-section">` with the standard
   shape: `nd-sec-num`, `nd-sec-title`, `nd-sec-sub`, then content
4. Add a matching link in the chapter's sub-nav (`<nav class="nd-subnav">`)
5. If the section has JS, add it to the chapter's IIFE at the bottom of the pane
6. If the section uses new CSS, prefix the classes (`.nd-*`, `.c2-*`, `.t3-*`,
   or chapter-specific)
7. Commit and push — the deploy syntax check catches breakage

### Add a glossary term

1. Open `rayvenet.html`, find the `GLOSSARY = {` object in the student-layer
   `<script>` near the bottom
2. Add `"TERM": "<b>Definition.</b> Body…"`
3. Term will auto-wrap on first occurrence per section across all chapters

### Deploy

```bash
cd "/Users/malhotra/Desktop/GW/Third Semester/Rayve Project/rebuild"
git add <files>
git commit -m "<message>"
git push origin main
```

GitHub Actions handles minify + deploy. ~60-90 seconds to live.

### Recover from "site is down"

See `OPERATIONS.md` § "Recovery". Most likely cause: repo was flipped to
Private. Flip it back to Public.

### Verify live deploy

```bash
curl -sI https://rayvelabs.com/ | head -5
curl -sI https://rayvelabs.com/rayvenet.html | head -5
```

200 = up. `Site not found · GitHub Pages` = Pages misconfigured or repo private.

---

## Owners

- **Rayve Malhotra** · rayvemalhotra@gmail.com · GitHub: @rayvemalhotra
- **Dr. Ravinder Mallarapu** (attribution; not an operator of this site)

For issues / feedback: open at https://github.com/rayvemalhotra/rayvelabs/issues
or email Rayve directly.

---

*This file is read by Claude Code (and any other agent) at the start of every
session. Keep it accurate; it's the working memory of the project.*
