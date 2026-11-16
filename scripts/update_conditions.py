#!/usr/bin/env python3
"""Refresh conditions.json with each resort's lift & trail report.

Reads the resort report embedded in each OpenSnow snow-report page
(the page's __NUXT_DATA__ payload) and writes one small JSON file the
dashboard can load from its own origin (no CORS problems).

Standard library only. If a resort can't be fetched, its previous entry
is kept so one bad request never blanks the dashboard.
"""
import json, re, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

# dashboard id -> OpenSnow location slug
RESORTS = {
    "abasin": "arapahoebasin",
    "copper": "copper",
    "winterpark": "winterpark",
    "eldora": "eldora",
    "steamboat": "steamboat",
    "aspenmtn": "aspenmountain",
    "highlands": "aspenhighlands",
    "buttermilk": "buttermilk",
    "snowmass": "snowmass",
}
OUT = Path(__file__).resolve().parent.parent / "conditions.json"
UA = "Mozilla/5.0 (compatible; IkonSnowStakeDashboard/1.0; +https://github.com/thatsogretch/Ikon-Snow-Stake-Dashboard)"
NUXT_RE = re.compile(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', re.S)


def fetch(slug):
    req = urllib.request.Request(
        f"https://opensnow.com/location/{slug}/snow-report",
        headers={"User-Agent": UA, "Accept": "text/html"},
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        html = res.read().decode("utf-8", "replace")
    m = NUXT_RE.search(html)
    if not m:
        raise ValueError("no __NUXT_DATA__ payload")
    arr = json.loads(m.group(1))

    def at(i):
        return arr[i] if isinstance(i, int) and 0 <= i < len(arr) else None

    loc = next(
        v for v in arr
        if isinstance(v, dict) and "resort_report" in v and "slug" in v and at(v["slug"]) == slug
    )
    rep = at(loc["resort_report"]) or {}
    g = lambda k: at(rep[k]) if k in rep else None
    notes = re.sub(r"\s+", " ", g("status_notes") or "").strip()
    return {
        "status": g("status_display"),
        "detail": g("status_display_detail"),
        "lifts_open": g("lifts_open"),
        "lifts_total": g("lifts_total"),
        "runs_open": g("runs_open"),
        "runs_total": g("runs_total"),
        "acres_open": g("area_open"),
        "acres_total": g("area_total"),
        "percent_open": g("percent_open"),
        "surface": g("conditions") or None,
        "notes": notes[:600] or None,
        "reported_at": g("display_at"),
        "terrain_url": at(loc.get("terrain_status_url")),
    }


def main():
    try:
        data = json.loads(OUT.read_text())
    except Exception:
        data = {"resorts": {}}
    ok = 0
    for rid, slug in RESORTS.items():
        try:
            data["resorts"][rid] = fetch(slug)
            ok += 1
            print(f"ok   {rid}: {data['resorts'][rid]['detail']}")
        except Exception as e:  # keep the previous entry
            print(f"FAIL {rid}: {e}", file=sys.stderr)
    if ok:
        data["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        data["source"] = "OpenSnow resort reports"
        OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"{ok}/{len(RESORTS)} resorts updated")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
