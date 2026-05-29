# RayveLabs — Operations Runbook

Everything needed to recover rayvelabs.com from scratch. Treat as the source
of truth for DNS, hosting, and accounts. Update this file whenever any of
those change.

---

## Owners

- **Primary**: Rayve Malhotra
- **Recovery email**: rayvemalhotra@gmail.com
- **Alt email**: manuduction@gmail.com

## Stack

| Layer       | Provider           | What it does                       |
|-------------|--------------------|------------------------------------|
| Domain      | Squarespace        | Registrar + DNS                    |
| Hosting     | GitHub Pages       | Static file hosting + HTTPS        |
| Repository  | GitHub             | Source of truth (rayvemalhotra/rayvelabs) |
| Email       | Gmail              | Owner + recovery                   |

## Critical invariant

The repository **MUST stay public**. GitHub Pages is free only on public
repos. Flipping the repo to private silently turns Pages off and takes the
site down. If you want private source, either upgrade to GitHub Pro
($4/mo) or move hosting to Cloudflare Pages / Netlify (both free with
private GitHub repos).

---

## DNS records (Squarespace)

These point rayvelabs.com at GitHub Pages and verify domain ownership.

### Apex (rayvelabs.com) — A records → GitHub Pages

| Type | Host | Value           | TTL  |
|------|------|-----------------|------|
| A    | @    | 185.199.108.153 | auto |
| A    | @    | 185.199.109.153 | auto |
| A    | @    | 185.199.110.153 | auto |
| A    | @    | 185.199.111.153 | auto |

### www subdomain → user.github.io

| Type  | Host | Value                       | TTL  |
|-------|------|-----------------------------|------|
| CNAME | www  | rayvemalhotra.github.io.    | auto |

### Domain verification TXT (required by GitHub for the custom domain)

| Type | Host                                  | Value                            | TTL  |
|------|---------------------------------------|----------------------------------|------|
| TXT  | _github-pages-challenge-rayvemalhotra | 5d924cf391e0fce293f450ebac01de   | auto |

> If GitHub rotates the verification token, replace the TXT value with the
> new one from https://github.com/settings/pages_verified_domains/rayvelabs.com.

---

## GitHub Pages settings

Found at https://github.com/rayvemalhotra/rayvelabs/settings/pages.

- **Source**: Deploy from a branch
- **Branch**: `main`
- **Folder**: `/ (root)`
- **Custom domain**: `rayvelabs.com`
- **Enforce HTTPS**: ON (auto-renews via Let's Encrypt)

The `.nojekyll` file in the repo root disables Jekyll so files publish as-is.
The `CNAME` file (containing `rayvelabs.com`) tells Pages which domain to
serve.

---

## Recovery — "the site is down"

Run these checks in order. The first one that fails tells you the layer to fix.

### 1. DNS resolves to GitHub Pages

```bash
dig rayvelabs.com +short
# Expected: the four 185.199.x.153 addresses above
```

If different, fix the A records at Squarespace.

### 2. HTTPS responds 200

```bash
curl -sI https://rayvelabs.com/ | head -5
```

- `404 Site not found · GitHub Pages` → Pages is off or the custom domain
  is misconfigured. Go to repo Settings → Pages and re-check Source,
  Custom domain, and that the repo is still public.
- TLS error → cert expired; toggle Enforce HTTPS off then on, or remove
  the custom domain and re-add it.

### 3. Latest commit deployed

```bash
curl -sI https://rayvelabs.com/ | grep -i last-modified
```

Compare against `git log -1`. If stale, check:
- The `pages build and deployment` workflow at
  https://github.com/rayvemalhotra/rayvelabs/actions
- Push an empty commit to retrigger:
  `git commit --allow-empty -m "trigger" && git push`

### 4. Domain verification

If Pages settings show "verification needed" for rayvelabs.com, re-add the
TXT record from the section above, wait 5 minutes, then click Verify on
https://github.com/settings/pages_verified_domains/rayvelabs.com.

---

## Recovery — "I lost access to GitHub"

1. Use the GitHub account recovery flow via your recovery email.
2. If 2FA codes are also lost, present the saved **recovery codes** (you
   stored these in your password manager when you turned on 2FA — this
   runbook exists partly so that fact lives somewhere).
3. If both email and codes are lost, GitHub's identity-verification process
   takes several days. In the meantime, the site keeps serving from the
   last deployed state — no action visitors will notice.

## Recovery — "I lost the domain"

If the domain expires or is hijacked at Squarespace:
- All A records and the TXT verification are documented above. After
  recovering the registrar account, recreate them.
- The repository, source, and Pages settings are unaffected. As soon as DNS
  is restored, the site comes back.

---

## Routine maintenance

- **Quarterly**: confirm domain auto-renew is on at Squarespace; confirm
  Enforce HTTPS is still on; confirm 2FA recovery codes are still valid.
- **On every dependency change**: re-check the CSP meta in `index.html` and
  `rayvenet.html` — if you add an external CDN, you must allow it.
- **Annually**: rotate the GitHub Pages domain verification TXT if GitHub
  prompts.

## Backup strategy

The repository itself is the backup; GitHub holds all history. Two
additional safeguards:

1. A local clone at `~/Desktop/GW/Third Semester/Rayve Project/rebuild`.
2. Optional cold backup: weekly GitHub Action that uploads a `git bundle`
   to Backblaze B2 or S3 (template in `.github/workflows/backup.yml.example`,
   uncomment + add credentials when ready).
