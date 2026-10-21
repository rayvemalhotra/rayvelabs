# Publishing to /writing

1. Create `writing/posts/YYYY-MM-DD-your-slug.md` with frontmatter:

   ```
   ---
   title: Your title
   date: 2026-10-17
   topic: signal            # OPTIONAL — omit it; add topics only once a cluster forms
   summary: One sentence shown on the index.
   tags: [optional, tags]
   draft: false             # true = not published
   ---
   Markdown body…
   ```

2. Commit + push to `main`. CI renders it to `/writing/<slug>/` (or `/writing/<topic>/<slug>/` if you gave it a topic),
   rebuilds the writing index (one flat list, newest first), the RSS feed, and the homepage strip.

3. Topics are optional. Add one to `writing/topics.json` only when 4–5 pieces cluster naturally.

Local preview: `npm i marked --no-save && node scripts/build-writing.mjs --out /tmp/site` then open `/tmp/site/writing/index.html`.
