# Metric definitions & thresholds

Thresholds follow [web.dev Core Web Vitals](https://web.dev/articles/vitals) and Lighthouse scoring. A metric is **Good** at/under the good bound, **Needs Improvement** up to the second bound, **Poor** above it.

## Lab metrics (Lighthouse — simulated single load)

| Metric | What it measures | Good | Needs Improvement | Poor |
|---|---|---|---|---|
| First Contentful Paint (FCP) | Time to first text/image painted | ≤ 1.8 s | ≤ 3.0 s | > 3.0 s |
| Largest Contentful Paint (LCP) | Time to largest above-the-fold element | ≤ 2.5 s | ≤ 4.0 s | > 4.0 s |
| Total Blocking Time (TBT) | Main-thread blocking between FCP and TTI (lab proxy for INP) | ≤ 200 ms | ≤ 600 ms | > 600 ms |
| Cumulative Layout Shift (CLS) | Visual stability (unitless) | ≤ 0.10 | ≤ 0.25 | > 0.25 |
| Speed Index | How quickly content is visually populated | ≤ 3.4 s | ≤ 5.8 s | > 5.8 s |
| Time to Interactive (TTI) | Time until reliably interactive | ≤ 3.8 s | ≤ 7.3 s | > 7.3 s |

## Field metrics (CrUX — real Chrome users, trailing 28 days, 75th percentile)

| Metric | Good | Needs Improvement | Poor |
|---|---|---|---|
| FCP | ≤ 1.8 s | ≤ 3.0 s | > 3.0 s |
| LCP | ≤ 2.5 s | ≤ 4.0 s | > 4.0 s |
| Interaction to Next Paint (INP) | ≤ 200 ms | ≤ 500 ms | > 500 ms |
| CLS | ≤ 0.10 | ≤ 0.25 | > 0.25 |
| Time to First Byte (TTFB) | ≤ 800 ms | ≤ 1.8 s | > 1.8 s |

> The PSI API returns each field metric with its own `category` of `FAST` / `AVERAGE` / `SLOW`. The script trusts that classification directly (mapped to Good / Needs Improvement / Poor) rather than re-deriving from percentiles.

## Category scores (0–100)

Lighthouse category score bands (used for the gauges):

- **90–100** → Good (green)
- **50–89** → Needs Improvement (amber)
- **0–49** → Poor (red)

Performance category weighting (Lighthouse 10+): FCP 10%, Speed Index 10%, LCP 25%, TBT 30%, CLS 25%. The single Performance score is the weighted blend — a low TBT/LCP dominates.

## Lab vs. field — which to trust

- **Field (CrUX)** is what real users actually experienced. It's the source of truth for whether the site is fast *in the wild*, but only exists for pages/origins with enough Chrome traffic.
- **Lab (Lighthouse)** is a reproducible, debuggable single run on Google's hardware with a throttled connection. Use it to diagnose *why* and to test changes — it's always available, even for brand-new pages.
- When they disagree, field wins for "is it a problem?"; lab wins for "what's causing it?".
