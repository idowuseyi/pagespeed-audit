# PageSpeed Insights API (v5) reference

## Endpoint

```
GET https://www.googleapis.com/pagespeedonline/v5/runPagespeed
```

## Query parameters

| Param | Required | Notes |
|---|---|---|
| `url` | yes | Fully-qualified, public URL (`https://example.com`). PSI must be able to reach it — no localhost/authed pages. |
| `strategy` | no | `mobile` (default) or `desktop`. Send one request per strategy. |
| `category` | no | Repeatable. Valid: `performance`, `accessibility`, `best-practices`, `seo`. **`pwa` was removed in Lighthouse 12 — requesting it returns HTTP 400.** Omitting `category` returns performance only. |
| `locale` | no | Report locale, e.g. `en`, `es`, `ja`. |
| `key` | no | API key. Raises quota; see below. |
| `utm_campaign`, `utm_source` | no | Attribution only. |

The script sends `category` once per requested category and only appends `key` when `PAGESPEED_API_KEY` is set in the environment.

## Response shape (fields the script reads)

```
{
  "id": "https://example.com/",
  "analysisUTCTimestamp": "...",
  "lighthouseResult": {
    "finalDisplayedUrl": "...",
    "lighthouseVersion": "12.x",
    "fetchTime": "...",
    "categories": {
      "performance":    { "score": 0.98, ... },
      "accessibility":  { "score": 0.95, ... },
      "best-practices": { "score": 1.0,  ... },
      "seo":            { "score": 0.92, ... }
    },
    "audits": {
      "first-contentful-paint":   { "numericValue": 1234, "displayValue": "1.2 s", "score": 0.99 },
      "largest-contentful-paint": { ... },
      "total-blocking-time":      { ... },
      "cumulative-layout-shift":  { ... },
      "speed-index":              { ... },
      "interactive":              { ... },
      "<opportunity audits>":     { "details": { "type": "opportunity", "overallSavingsMs": 450 }, ... }
    }
  },
  "loadingExperience":       { "overall_category": "FAST", "metrics": { "LARGEST_CONTENTFUL_PAINT_MS": { "percentile": 2100, "category": "FAST" }, ... } },
  "originLoadingExperience": { ... same shape, aggregated across the whole origin ... }
}
```

- `loadingExperience` = field data for **this specific URL**; `originLoadingExperience` = field data for the **whole origin**. The script prefers the URL-level data and falls back to origin-level, and reports which scope it used. Either may be absent for low-traffic sites.
- CrUX field metric keys: `FIRST_CONTENTFUL_PAINT_MS`, `LARGEST_CONTENTFUL_PAINT_MS`, `INTERACTION_TO_NEXT_PAINT`, `CUMULATIVE_LAYOUT_SHIFT_SCORE`, `EXPERIMENTAL_TIME_TO_FIRST_BYTE`. The CLS score is an integer ×100 (e.g. `10` → 0.10).

## API key (optional)

Keyless requests work but are rate-limited (roughly a few per minute per IP; bursts return **HTTP 429**). A free key raises the quota to **25,000 requests/day**.

To create one:
1. Go to <https://console.cloud.google.com/apis/credentials> (or the [PSI get-a-key page](https://developers.google.com/speed/docs/insights/v5/get-started)).
2. Enable the **PageSpeed Insights API** for your project.
3. Create an **API key** credential.
4. Export it so the script picks it up:
   ```bash
   export PAGESPEED_API_KEY="AIza...your-key..."
   ```
   Add that line to `~/.bashrc` / `~/.zshrc` to persist it.

The script never prints the key and reports only whether one was used.
