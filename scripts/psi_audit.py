#!/usr/bin/env python3
"""
psi_audit.py — Analyze a website's speed & health via the Google PageSpeed
Insights API (v5, runPagespeed) and emit a JSON + Markdown + HTML report.

Stdlib only (urllib, json) — no pip install required.

Usage:
    python3 psi_audit.py <URL> [options]

Options:
    --strategy    Comma list of mobile,desktop        (default: mobile,desktop)
    --categories  Comma list of Lighthouse categories (default: performance,accessibility,best-practices,seo)
    --locale      Report locale                        (default: en)
    --out-dir     Directory for output files           (default: current dir)
    --timeout     Per-request timeout seconds           (default: 120)

Environment:
    PAGESPEED_API_KEY  Optional. Raises quota to 25k/day. Keyless works but is rate-limited.

Exit codes:
    0  success (at least one strategy reported)
    1  usage / argument error
    2  all requested strategies failed (network/API error)
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

DEFAULT_CATEGORIES = ["performance", "accessibility", "best-practices", "seo"]
DEFAULT_STRATEGIES = ["mobile", "desktop"]

# Lab audits we surface, in display order. (audit id -> friendly label)
LAB_METRICS = [
    ("first-contentful-paint", "First Contentful Paint (FCP)"),
    ("largest-contentful-paint", "Largest Contentful Paint (LCP)"),
    ("total-blocking-time", "Total Blocking Time (TBT)"),
    ("cumulative-layout-shift", "Cumulative Layout Shift (CLS)"),
    ("speed-index", "Speed Index"),
    ("interactive", "Time to Interactive (TTI)"),
]

# Field (CrUX) metrics we surface. (crux key -> friendly label)
FIELD_METRICS = [
    ("FIRST_CONTENTFUL_PAINT_MS", "First Contentful Paint (FCP)"),
    ("LARGEST_CONTENTFUL_PAINT_MS", "Largest Contentful Paint (LCP)"),
    ("INTERACTION_TO_NEXT_PAINT", "Interaction to Next Paint (INP)"),
    ("CUMULATIVE_LAYOUT_SHIFT_SCORE", "Cumulative Layout Shift (CLS)"),
    ("EXPERIMENTAL_TIME_TO_FIRST_BYTE", "Time to First Byte (TTFB)"),
]

# Thresholds for lab numericValue. Units: ms except CLS (unitless).
# (good_max, needs_improvement_max) — above NI = poor.
LAB_THRESHOLDS = {
    "first-contentful-paint": (1800, 3000),
    "largest-contentful-paint": (2500, 4000),
    "total-blocking-time": (200, 600),
    "cumulative-layout-shift": (0.1, 0.25),
    "speed-index": (3400, 5800),
    "interactive": (3800, 7300),
}

CATEGORY_LABELS = {
    "performance": "Performance",
    "accessibility": "Accessibility",
    "best-practices": "Best Practices",
    "seo": "SEO",
    "pwa": "PWA",
}


def log(msg):
    print(msg, file=sys.stderr)


def classify_lab(audit_id, numeric_value):
    """Return 'good' | 'ni' | 'poor' | 'na' for a lab metric numericValue."""
    if numeric_value is None:
        return "na"
    bands = LAB_THRESHOLDS.get(audit_id)
    if not bands:
        return "na"
    good_max, ni_max = bands
    if numeric_value <= good_max:
        return "good"
    if numeric_value <= ni_max:
        return "ni"
    return "poor"


def score_band(score_0_100):
    """Lighthouse category score bands: >=90 good, 50-89 ni, <50 poor."""
    if score_0_100 is None:
        return "na"
    if score_0_100 >= 90:
        return "good"
    if score_0_100 >= 50:
        return "ni"
    return "poor"


def crux_band(category_str):
    """Map CrUX category (FAST/AVERAGE/SLOW) to our band names."""
    return {"FAST": "good", "AVERAGE": "ni", "SLOW": "poor"}.get(category_str, "na")


def fetch(url, strategy, categories, locale, timeout):
    """Call PSI once. Returns (json_dict, error_str). One of them is None."""
    params = [("url", url), ("strategy", strategy), ("locale", locale)]
    for cat in categories:
        params.append(("category", cat))
    key = os.environ.get("PAGESPEED_API_KEY")
    if key:
        params.append(("key", key))
    query = urllib.parse.urlencode(params)
    full = f"{PSI_ENDPOINT}?{query}"
    req = urllib.request.Request(full, headers={"User-Agent": "pagespeed-audit-skill/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data, None
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")
            detail = json.loads(body).get("error", {}).get("message", body)
        except Exception:
            detail = body or str(e)
        hint = ""
        if e.code == 429:
            hint = " (quota exceeded — set PAGESPEED_API_KEY for a higher limit)"
        elif e.code == 400:
            hint = " (check the URL is public and fully-qualified, e.g. https://example.com)"
        return None, f"HTTP {e.code} for strategy '{strategy}'{hint}: {detail}"
    except urllib.error.URLError as e:
        return None, f"Network error for strategy '{strategy}': {e.reason}"
    except (TimeoutError, json.JSONDecodeError) as e:
        return None, f"Failed for strategy '{strategy}': {e}"


def extract(data, categories):
    """Pull the fields we care about out of one PSI response."""
    lh = data.get("lighthouseResult", {}) or {}
    audits = lh.get("audits", {}) or {}
    cats = lh.get("categories", {}) or {}

    # Category scores (0-100)
    scores = {}
    for cat in categories:
        c = cats.get(cat)
        if c and c.get("score") is not None:
            scores[cat] = round(c["score"] * 100)
        else:
            scores[cat] = None

    # Lab metrics
    lab = []
    for audit_id, label in LAB_METRICS:
        a = audits.get(audit_id)
        if not a:
            continue
        nv = a.get("numericValue")
        lab.append({
            "id": audit_id,
            "label": label,
            "display": a.get("displayValue", "—"),
            "numeric": nv,
            "band": classify_lab(audit_id, nv),
        })

    # Field data (page-level, fallback to origin-level)
    def read_field(container):
        if not container:
            return None, {}
        metrics = container.get("metrics", {}) or {}
        out = []
        for key, label in FIELD_METRICS:
            m = metrics.get(key)
            if not m:
                continue
            out.append({
                "id": key,
                "label": label,
                "percentile": m.get("percentile"),
                "category": m.get("category"),
                "band": crux_band(m.get("category")),
            })
        overall = container.get("overall_category")
        return overall, out

    page_overall, page_field = read_field(data.get("loadingExperience"))
    origin_overall, origin_field = read_field(data.get("originLoadingExperience"))
    if page_field:
        field = {"scope": "this URL", "overall": page_overall, "metrics": page_field}
    elif origin_field:
        field = {"scope": "whole origin", "overall": origin_overall, "metrics": origin_field}
    else:
        field = None

    # Opportunities (estimated savings) + failing audits
    opportunities = []
    failing = []
    for audit_id, a in audits.items():
        details = a.get("details") or {}
        score = a.get("score")
        if details.get("type") == "opportunity":
            overall_ms = details.get("overallSavingsMs") or a.get("numericValue") or 0
            if overall_ms and overall_ms > 0:
                opportunities.append({
                    "id": audit_id,
                    "title": a.get("title", audit_id),
                    "savings_ms": round(overall_ms),
                    "display": a.get("displayValue", ""),
                })
        # Failing (scored) audits worth flagging
        if score is not None and score < 0.9 and a.get("scoreDisplayMode") in ("numeric", "binary"):
            failing.append({
                "id": audit_id,
                "title": a.get("title", audit_id),
                "score": round(score * 100),
                "display": a.get("displayValue", ""),
            })
    opportunities.sort(key=lambda o: o["savings_ms"], reverse=True)
    failing.sort(key=lambda f: f["score"])

    return {
        "final_url": lh.get("finalDisplayedUrl") or lh.get("finalUrl") or lh.get("requestedUrl"),
        "fetch_time": lh.get("fetchTime"),
        "lighthouse_version": lh.get("lighthouseVersion"),
        "scores": scores,
        "lab": lab,
        "field": field,
        "opportunities": opportunities[:8],
        "failing": failing[:10],
    }


# ----------------------------- Rendering ------------------------------------

BAND_LABEL = {"good": "Good", "ni": "Needs Improvement", "poor": "Poor", "na": "N/A"}
BAND_EMOJI = {"good": "🟢", "ni": "🟠", "poor": "🔴", "na": "⚪"}


def render_markdown(url, generated, used_key, categories, results):
    lines = []
    lines.append(f"# PageSpeed Insights Report — {url}")
    lines.append("")
    lines.append(f"- **Generated:** {generated}")
    lines.append(f"- **Source:** Google PageSpeed Insights API v5 (Lighthouse, lab) + CrUX (field)")
    lines.append(f"- **API key used:** {'yes' if used_key else 'no (keyless)'}")
    lines.append("")

    for strategy, res in results:
        if res.get("error"):
            lines.append(f"## {strategy.capitalize()} — ⚠️ failed")
            lines.append("")
            lines.append(f"> {res['error']}")
            lines.append("")
            continue
        ext = res["data"]
        lines.append(f"## {strategy.capitalize()}")
        lines.append("")
        lines.append(f"Analyzed URL: `{ext['final_url']}` · Lighthouse {ext['lighthouse_version']}")
        lines.append("")

        # Category scores
        lines.append("### Category scores")
        lines.append("")
        lines.append("| Category | Score | Status |")
        lines.append("|---|---:|---|")
        for cat in categories:
            s = ext["scores"].get(cat)
            band = score_band(s)
            label = CATEGORY_LABELS.get(cat, cat)
            sval = f"{s}" if s is not None else "—"
            lines.append(f"| {label} | {sval} | {BAND_EMOJI[band]} {BAND_LABEL[band]} |")
        lines.append("")

        # Lab metrics
        lines.append("### Lab metrics (simulated)")
        lines.append("")
        lines.append("| Metric | Value | Status |")
        lines.append("|---|---|---|")
        for m in ext["lab"]:
            lines.append(f"| {m['label']} | {m['display']} | {BAND_EMOJI[m['band']]} {BAND_LABEL[m['band']]} |")
        lines.append("")

        # Field data
        lines.append("### Field data (real users, CrUX)")
        lines.append("")
        if ext["field"]:
            f = ext["field"]
            lines.append(f"Scope: **{f['scope']}** · Overall: {BAND_LABEL.get(crux_band(f['overall']), f['overall'] or '—')}")
            lines.append("")
            lines.append("| Metric | 75th percentile | Status |")
            lines.append("|---|---|---|")
            for m in f["metrics"]:
                val = m["percentile"]
                unit = "" if m["id"] == "CUMULATIVE_LAYOUT_SHIFT_SCORE" else " ms"
                disp = f"{val / 100:.2f}" if m["id"] == "CUMULATIVE_LAYOUT_SHIFT_SCORE" and val is not None else f"{val}{unit}"
                lines.append(f"| {m['label']} | {disp} | {BAND_EMOJI[m['band']]} {BAND_LABEL[m['band']]} |")
            lines.append("")
        else:
            lines.append("_No field data available — this URL/origin has insufficient real-user traffic in the CrUX dataset._")
            lines.append("")

        # Opportunities
        if ext["opportunities"]:
            lines.append("### Top opportunities (estimated savings)")
            lines.append("")
            for o in ext["opportunities"]:
                extra = f" — {o['display']}" if o["display"] else ""
                lines.append(f"- **{o['title']}** — ~{o['savings_ms']} ms{extra}")
            lines.append("")

        # Failing audits
        if ext["failing"]:
            lines.append("### Failing / weak audits")
            lines.append("")
            for fa in ext["failing"]:
                extra = f" — {fa['display']}" if fa["display"] else ""
                lines.append(f"- **{fa['title']}** (score {fa['score']}){extra}")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("_Lab data is a simulated single load in a controlled environment; field data reflects real Chrome users over the trailing 28 days. Thresholds follow web.dev Core Web Vitals guidance._")
    lines.append("")
    return "\n".join(lines)


def _score_ring(score, band):
    """Inline SVG gauge for a category score."""
    if score is None:
        return '<div class="gauge gauge-na"><span>—</span></div>'
    pct = max(0, min(100, score))
    circ = 2 * 3.14159 * 42
    offset = circ * (1 - pct / 100)
    return (
        f'<div class="gauge gauge-{band}">'
        f'<svg viewBox="0 0 100 100" width="88" height="88">'
        f'<circle cx="50" cy="50" r="42" class="ring-bg"/>'
        f'<circle cx="50" cy="50" r="42" class="ring-fg" '
        f'stroke-dasharray="{circ:.1f}" stroke-dashoffset="{offset:.1f}" '
        f'transform="rotate(-90 50 50)"/>'
        f'</svg><span class="gauge-num">{score}</span></div>'
    )


def render_html_body(url, generated, used_key, categories, results):
    """Return an Artifact-ready HTML fragment (no <html>/<head>/<body>)."""
    parts = []
    parts.append('<main class="psi">')
    parts.append('<header class="psi-head">')
    parts.append(f'<h1>PageSpeed Report</h1>')
    parts.append(f'<p class="psi-url">{_esc(url)}</p>')
    parts.append('<p class="psi-meta">'
                 f'<span>{_esc(generated)}</span>'
                 f'<span class="badge">{"keyed" if used_key else "keyless"}</span>'
                 '<span>Lighthouse lab + CrUX field</span></p>')
    parts.append('</header>')

    for strategy, res in results:
        parts.append(f'<section class="strategy"><h2>{strategy.capitalize()}</h2>')
        if res.get("error"):
            parts.append(f'<div class="error">⚠️ {_esc(res["error"])}</div></section>')
            continue
        ext = res["data"]

        # Score gauges
        parts.append('<div class="gauges">')
        for cat in categories:
            s = ext["scores"].get(cat)
            band = score_band(s)
            parts.append('<div class="gauge-cell">'
                         + _score_ring(s, band)
                         + f'<span class="gauge-label">{_esc(CATEGORY_LABELS.get(cat, cat))}</span></div>')
        parts.append('</div>')

        # Lab metrics table
        parts.append('<h3>Lab metrics <small>(simulated load)</small></h3>')
        parts.append('<div class="tbl-wrap"><table><thead><tr>'
                     '<th>Metric</th><th>Value</th><th>Status</th></tr></thead><tbody>')
        for m in ext["lab"]:
            parts.append(f'<tr><td>{_esc(m["label"])}</td><td>{_esc(m["display"])}</td>'
                         f'<td><span class="chip chip-{m["band"]}">{BAND_LABEL[m["band"]]}</span></td></tr>')
        parts.append('</tbody></table></div>')

        # Field data
        parts.append('<h3>Field data <small>(real users · CrUX)</small></h3>')
        if ext["field"]:
            f = ext["field"]
            parts.append(f'<p class="scope">Scope: <strong>{_esc(f["scope"])}</strong></p>')
            parts.append('<div class="tbl-wrap"><table><thead><tr>'
                         '<th>Metric</th><th>75th pct</th><th>Status</th></tr></thead><tbody>')
            for m in f["metrics"]:
                val = m["percentile"]
                if m["id"] == "CUMULATIVE_LAYOUT_SHIFT_SCORE" and val is not None:
                    disp = f"{val / 100:.2f}"
                elif val is not None:
                    disp = f"{val} ms"
                else:
                    disp = "—"
                parts.append(f'<tr><td>{_esc(m["label"])}</td><td>{disp}</td>'
                             f'<td><span class="chip chip-{m["band"]}">{BAND_LABEL[m["band"]]}</span></td></tr>')
            parts.append('</tbody></table></div>')
        else:
            parts.append('<p class="nofield">No field data — insufficient real-user traffic in CrUX.</p>')

        # Opportunities
        if ext["opportunities"]:
            parts.append('<h3>Top opportunities</h3><ul class="opps">')
            for o in ext["opportunities"]:
                extra = f' — {_esc(o["display"])}' if o["display"] else ""
                parts.append(f'<li><strong>{_esc(o["title"])}</strong>'
                             f'<span class="save">~{o["savings_ms"]} ms</span>{extra}</li>')
            parts.append('</ul>')

        # Failing audits
        if ext["failing"]:
            parts.append('<h3>Failing / weak audits</h3><ul class="fails">')
            for fa in ext["failing"]:
                extra = f' — {_esc(fa["display"])}' if fa["display"] else ""
                parts.append(f'<li><strong>{_esc(fa["title"])}</strong> '
                             f'<span class="score">{fa["score"]}</span>{extra}</li>')
            parts.append('</ul>')

        parts.append('</section>')

    parts.append('<footer class="psi-foot">Lab = simulated single load. '
                 'Field = real Chrome users, trailing 28 days. '
                 'Thresholds per web.dev Core Web Vitals.</footer>')
    parts.append('</main>')
    return "\n".join(parts)


def _esc(s):
    if s is None:
        return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def build_html(template, body):
    return template.replace("<!--PSI_BODY-->", body)


def domain_of(url):
    netloc = urllib.parse.urlparse(url).netloc or url
    return netloc.replace(":", "_").replace("/", "_") or "site"


def main():
    p = argparse.ArgumentParser(description="PageSpeed Insights audit → JSON + Markdown + HTML")
    p.add_argument("url", help="Full URL to audit, e.g. https://example.com")
    p.add_argument("--strategy", default=",".join(DEFAULT_STRATEGIES))
    p.add_argument("--categories", default=",".join(DEFAULT_CATEGORIES))
    p.add_argument("--locale", default="en")
    p.add_argument("--out-dir", default=".")
    p.add_argument("--timeout", type=int, default=120)
    args = p.parse_args()

    url = args.url
    if not urllib.parse.urlparse(url).scheme:
        url = "https://" + url

    strategies = [s.strip() for s in args.strategy.split(",") if s.strip()]
    categories = [c.strip() for c in args.categories.split(",") if c.strip()]
    if "pwa" in categories:
        log("Note: dropping 'pwa' — removed in Lighthouse 12; PSI rejects it.")
        categories = [c for c in categories if c != "pwa"]

    used_key = bool(os.environ.get("PAGESPEED_API_KEY"))
    os.makedirs(args.out_dir, exist_ok=True)

    results = []
    raw = {}
    ok_count = 0
    for strategy in strategies:
        log(f"Fetching {strategy} for {url} ...")
        data, err = fetch(url, strategy, categories, args.locale, args.timeout)
        if err:
            log(f"  ✗ {err}")
            results.append((strategy, {"error": err}))
        else:
            results.append((strategy, {"data": extract(data, categories)}))
            raw[strategy] = data
            ok_count += 1
            log(f"  ✓ {strategy} done")

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    date_slug = datetime.now(timezone.utc).strftime("%Y%m%d")
    base = f"psi-{domain_of(url)}-{date_slug}"
    out = args.out_dir.rstrip("/")

    # JSON (merged raw + extracted)
    json_path = f"{out}/{base}.json"
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump({
            "url": url, "generated": generated, "used_key": used_key,
            "categories": categories,
            "extracted": {s: r.get("data") or {"error": r.get("error")} for s, r in results},
            "raw": raw,
        }, fh, indent=2)

    # Markdown
    md = render_markdown(url, generated, used_key, categories, results)
    md_path = f"{out}/{base}.md"
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(md)

    # HTML (fill template if present, else standalone-ish fragment)
    body = render_html_body(url, generated, used_key, categories, results)
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "..", "assets", "report_template.html")
    if os.path.exists(template_path):
        with open(template_path, encoding="utf-8") as fh:
            template = fh.read()
        html = build_html(template, body)
    else:
        html = body
    html_path = f"{out}/{base}.html"
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(html)

    log("")
    log(f"Wrote:\n  {json_path}\n  {md_path}\n  {html_path}")

    if ok_count == 0:
        log("ERROR: all strategies failed — no usable report data.")
        sys.exit(2)


if __name__ == "__main__":
    main()
