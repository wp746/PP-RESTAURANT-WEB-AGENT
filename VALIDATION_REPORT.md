# PP Restaurant Web Agent v0.1 — Verification report

Date: 2026-10-10. This report distinguishes completed checks from untested external integrations.

## Verified in local runtime

- Python package code compiles; `ppweb` CLI entrypoint launches and advertises `run/bootstrap/remove`.
- `pytest`: 8 tests passed (ZIP traversal/bomb rejection, conservative fact extraction, multi-store preservation, stale directory refusal, HTML static audit, bad external link rejection, explicit replace protection).
- `examples/demo-site.zip` full **offline MOCK** execution: extract → process picture → build HTML/CSS/JS → Chromium screenshot at 390/1440/360/768 → merge staged full-site snapshot ZIP. Demo is watermarked and blocked from publication.
- Optional FastAPI browser upload interface responds on `/` and rejects unauthorized POST with HTTP 401; job queue serializes build/deploy to avoid race.
- Real currently known Pages root + `wangjiao/` contents were included as an initial historical reference based on the already approved `PP餐饮网站_Cloudflare_修复总入口_V2.zip` from this conversation. The live Pages project was **not modified** during agent development.
- GitHub connector available under account `wp746`; no `create repository` capability was exposed, so no standalone GitHub repo was created by this task. The complete project is packaged for owner upload.

## Not verified yet (requires external secret authorization / production provider)

- Cloudflare Pages publish via scoped API token: no `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID` supplied to this execution environment; no real publish invoked.
- Brand-specific model generation + model vision review: no API key/production text+vision model configured. Mock mode was used for smoke tests only and is not a quality benchmark.
- Repository push/pull workflow after user creates an independent GitHub repository.
- China mainland mobile data / in-app browser accessibility.
- Customer brand facts, menus, image rights and genuine business approval: only real source ZIP can establish those.
- Reference 25 site dynamic component implementations and commercial redistribution permissions: the built-in index is design guidance, not downloaded third-party code.

## Production blockers are deliberate

- No fake Cloudflare URL returned on missing token, unsupported owner approval, bad HTML, missing existing `sites/index.html`, broken browser rendering, or failed model visual QA.
- Existing merchant paths are never replaced unless `--replace` explicitly set.
- Raw merchant uploads and service secrets are excluded from Git; public artifacts must be previously approved.

## Next setup steps

1. Create empty independent GitHub repo `wp746/PP-RESTAURANT-WEB-AGENT` and upload code folder (not private inputs).
2. Configure production text/vision model keys in trusted secrets.
3. Issue a scoped Cloudflare Pages Write token and Account ID; do not share via chat.
4. Confirm `sites/` exactly matches live Pages production; only then allow any automatic deployment.
5. Run one end-to-end live tenant with genuine authorized input and compare mobile/desktop QA.
