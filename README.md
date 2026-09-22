# pagespeed-audit

A [Claude Code](https://claude.com/claude-code) skill that audits the speed and health of any public website using the **Google PageSpeed Insights API v5**. It runs Lighthouse remotely on Google's servers and merges in real-user **Chrome UX Report (CrUX)** field data. No local browser is needed.

For each URL it produces three reports:

| File | What it's for |
|---|---|
| `psi-<domain>-<date>.md` | A full Markdown report: category scores, lab metrics, field data, opportunities and failing audits |
| `psi-<domain>-<date>.json` | Raw and extracted data, for an audit trail or further processing |
| `psi-<domain>-<date>.html` | A self-contained HTML report, ready to publish as a shareable Claude Artifact |

It covers **Performance, Accessibility, Best Practices and SEO** for both **mobile and desktop**, plus the Core Web Vitals: LCP, INP, CLS, FCP and TTFB.

## Install

Clone the repo into your personal skills folder:

```bash
git clone git@github.com:idowuseyi/pagespeed-audit.git ~/.claude/skills/pagespeed-audit
```

Claude Code picks it up automatically. Ask something like *"Run a PageSpeed audit on https://example.com"*.

**Requirements:** Python 3 only. The script uses the standard library, so there's nothing to `pip install`.

## API key (recommended)

The script works without a key, but Google rate-limits keyless requests heavily and they often fail with **HTTP 429**. A free key raises the limit to 25,000 requests per day:

1. Enable the **PageSpeed Insights API** in the [Google Cloud console](https://console.cloud.google.com/apis/credentials) and create an API key.
2. Export the key:

   ```bash
   export PAGESPEED_API_KEY="AIza...your-key..."
   ```

The script never prints the key. Its output only says whether a key was used.

## Run the script directly

You can also run the script without Claude:

```bash
python3 scripts/psi_audit.py "https://example.com" --out-dir ./reports
```

| Flag | Default | Notes |
|---|---|---|
| `--strategy` | `mobile,desktop` | For example, `--strategy mobile` for a faster single run |
| `--categories` | `performance,accessibility,best-practices,seo` | `pwa` was removed in Lighthouse 12 and is dropped automatically |
| `--locale` | `en` | The report language |
| `--out-dir` | `.` | Where the three reports are written |
| `--timeout` | `120` | The per-request timeout, in seconds |

The script exits with code `2` when every strategy fails, for example because of a network error or a used-up quota.

## Layout

```
SKILL.md                     # Skill instructions that Claude follows
scripts/psi_audit.py         # Fetches, extracts and writes the reports (stdlib only)
assets/report_template.html  # The HTML report template
references/api.md            # PSI endpoint, parameters, response shape, key setup
references/metrics.md        # Metric thresholds and lab vs. field data explained
```

## Related

To profile a page running locally, or a page behind a login, use a Chrome DevTools-based skill such as `web-perf` instead. PageSpeed Insights can only reach public URLs.
