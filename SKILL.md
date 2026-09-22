---
name: pagespeed-audit
description: Analyze the speed, performance, and overall health of any public website URL using the Google PageSpeed Insights API (v5, runPagespeed). Runs Lighthouse remotely on Google's servers across Performance, Accessibility, Best Practices, and SEO, and merges in real-user CrUX field data (Core Web Vitals — LCP, INP, CLS, FCP, TTFB). Produces a Markdown report file, a raw JSON dump, and a polished shareable HTML report published as an Artifact. Use when asked to audit/analyze/measure/report a website's PageSpeed, Lighthouse score, load speed, Core Web Vitals, or site performance for a given URL. No local browser needed. (For live, interactive profiling of a locally-running page via Chrome DevTools instead, use the web-perf skill.)
---

# PageSpeed Audit

Point at any public URL and produce a detailed performance & health report from Google's PageSpeed Insights API. This skill hits the **remote** PSI REST API (Lighthouse-in-the-cloud + real-user CrUX field data) — it needs no local Chrome and works against any reachable public URL.

> **When NOT to use this:** if the user wants to profile a page running locally / behind auth, or step through a live trace interactively, use the `web-perf` skill (Chrome DevTools MCP) instead. This skill needs a public URL PSI can reach.

## What it produces

For a given URL it emits three files (default names `psi-<domain>-<date>.{json,md,html}`):
- **`.md`** — full Markdown report (category scores, lab metrics, field data, opportunities, failing audits) per strategy.
- **`.json`** — merged raw + extracted data, for audit trail or further processing.
- **`.html`** — a polished, self-contained report you publish as a shareable **Artifact**.

## Workflow

Copy this checklist and work through it:

```
PageSpeed audit:
- [ ] 1. Confirm URL + Python 3 available
- [ ] 2. Run psi_audit.py into a working dir
- [ ] 3. Read the .md, summarize scores + top fixes for the user
- [ ] 4. Publish the .html as an Artifact → share the link
- [ ] 5. Point the user to the .md / .json files
```

### 1. Preconditions
- You need a **fully-qualified public URL** (`https://…`). If the user gave a bare domain, the script prepends `https://`.
- Python 3 must be available (`python3 --version`). The script is **stdlib-only** — no `pip install`.
- An API key is **optional**. If `PAGESPEED_API_KEY` is set in the environment the script uses it (higher quota); otherwise it runs keyless. Don't block on a key. Only mention it if a run hits **HTTP 429** (quota). See `references/api.md` for creating one.

### 2. Run the script

From the skill directory (adjust the path to where this skill lives):

```bash
python3 scripts/psi_audit.py "<URL>" --out-dir "<working-or-scratch-dir>"
```

Defaults run **both** `mobile` and `desktop` strategies and **all four** categories (performance, accessibility, best-practices, seo). Useful flags:
- `--strategy mobile` — one strategy only (faster).
- `--categories performance` — speed only.
- `--locale es` — localized report.

Progress prints to stderr; the three output paths print at the end. Exit code `2` means every strategy failed (network/API) — surface the stderr message to the user, don't invent results.

### 3. Summarize for the user
Read the generated `.md` and give the user a tight inline summary: the headline **category scores** (mobile + desktop), the **Core Web Vitals** status, and the **top 2–3 opportunities/fixes** with their estimated savings. Be specific and quantified (e.g. "LCP 4.3 s — Poor; largest saving is deferring `main.js` (~610 ms)"). Distinguish lab vs. field: field data (if present) is what real users experienced; lab explains *why*. See `references/metrics.md` for thresholds and the lab-vs-field explainer.

### 4. Publish the HTML as an Artifact
The `.html` file is already an Artifact-ready fragment (inline `<style>`, no `<html>/<body>` wrapper, CSP-safe — no external fonts/JS). Publish it with the **Artifact** tool:
- `file_path`: the generated `.html`
- `title`: e.g. `PageSpeed Report — <domain>`
- `description`: one line naming the site and headline scores
- `favicon`: `⚡`

Return the shareable URL to the user. (The design is pre-calibrated; you don't need to restyle it. If the user asks for changes to the look, edit `assets/report_template.html` and re-run.)

### 5. Hand off the files
Tell the user where the `.md` and `.json` live so they can keep/commit or post-process them.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `HTTP 429 … quota exceeded` | Keyless rate limit hit. Set `PAGESPEED_API_KEY` (see `references/api.md`) and retry. |
| `HTTP 400 … check the URL` | URL not public/fully-qualified, or PSI can't reach it (localhost, auth wall, blocked bot). |
| "No field data" in the report | Normal for low-traffic URLs — CrUX only has field data for pages/origins with enough Chrome users. Lab data still reports. |
| One strategy failed, other succeeded | The report still renders the successful strategy and notes the failure — mention both to the user. |
| `pwa` requested → 400 | PWA category was removed in Lighthouse 12; the script auto-drops it. Don't request it. |

## Files in this skill
- `scripts/psi_audit.py` — the fetch + extract + report engine (stdlib only).
- `assets/report_template.html` — Artifact-ready HTML shell the script fills.
- `references/metrics.md` — metric definitions, thresholds, lab-vs-field.
- `references/api.md` — PSI endpoint, params, response shape, API-key setup.
