# Publishing to /writing

1. Create `writing/posts/YYYY-MM-DD-your-slug.md` with frontmatter:

   ```
   ---
   title: Your title
   date: 2026-10-17
   topic: discovery        # a slug from writing/topics.json
   summary: One sentence shown on the index.
   tags: [optional, tags]
   draft: false             # true = not published
   ---
   Markdown body…
   ```

2. Commit + push to `main`. CI renders it to `/writing/<topic>/<slug>/`, rebuilds the
   topic page, the writing index, the RSS feed, and the "Latest writing" strip on the homepage.

3. New topic? Add it to `writing/topics.json` first.

Local preview: `npm i marked --no-save && node scripts/build-writing.mjs --out /tmp/site` then open `/tmp/site/writing/index.html`.
