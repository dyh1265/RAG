# Portfolio polish: fix recruiter-feedback issues

## Problem
Outside review of the DocuMind repo flagged five concrete gaps that hold it
back from looking production-grade:

1. CI workflow triggers only on `main`, but the default branch is `master`,
   so the CI badge never updates and PRs never run checks.
2. README has no screenshots / GIF near the top — recruiters cannot see
   what the app does without reading code.
3. CI installs the backend, runs `pytest` and `ruff`, but never builds the
   frontend. A broken `npm run build` would ship unnoticed.
4. CORS is hardcoded to `allow_origins=["*"]`, which is fine for the demo
   but undermines the "production-grade" framing.
5. The README mentions eval workflows but never shows the actual numbers,
   so readers cannot tell whether retrieval quality is good.

## Plan
- [x] `ci.yml`: trigger on `main` **and** `master`
- [x] `eval.yml`: same
- [x] `ci.yml`: add a `frontend` job that runs `npm ci` + `npm run build`
- [x] `backend/core/config.py`: add `cors_allow_origins` (default `["*"]`,
      override with comma-separated env var `CORS_ALLOW_ORIGINS`)
- [x] `backend/api/main.py`: read the new setting; restrict methods/headers
      sensibly when not `*`
- [x] `.env.example`: document `CORS_ALLOW_ORIGINS`
- [x] `README.md`: add a `Demo` section near the top referencing
      `docs/images/{upload,chat,citations}.png|gif`
- [x] `docs/images/README.md`: explain what each image should show so the
      user can drop in screenshots without thinking
- [x] `README.md`: add a `Benchmarks` section with the CI-enforced
      thresholds, methodology, and how to regenerate real numbers
- [x] `eval.yml`: write a Markdown benchmark summary to
      `$GITHUB_STEP_SUMMARY` and upload it as an artifact, so the next eval
      run produces real numbers the user can paste into the README
- [x] Verify: `ruff check`, `ReadLints`, frontend `tsc -b` (lint-only)

## Review
- **Verification:** ruff clean on changed files; `ReadLints` clean.
- **Behavior diff:**
  - CI runs on master pushes/PRs and the badge actually reflects status.
  - A frontend build break now fails CI on PR.
  - CORS defaults stay open (`*`) so existing demos keep working, but
    setting `CORS_ALLOW_ORIGINS=https://docu.example.com` locks it down.
  - README shows benchmark thresholds + how to regenerate real numbers.
  - The next scheduled eval run produces a real benchmark table users can
    paste into the README.
- **Residual risks:**
  - Screenshots still need to be captured by the user and dropped into
    `docs/images/`. README will render with broken-image icons until then;
    the `docs/images/README.md` documents exactly what each shot should be.
  - Real benchmark numbers require running the eval workflow once (free on
    GitHub Actions).
