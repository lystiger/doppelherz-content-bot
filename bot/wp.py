"""Read posts and products from the client's WordPress/WooCommerce REST API.

Polling /wp-json needs no plugin on the client's site, which suits a pilot.
Production can switch to a webhook plugin for lower latency.
"""
import html
import json
import re
import urllib.request

BASE = "https://doppelherz.vn"
UA = {"User-Agent": "Mozilla/5.0 (DoppelherzContentBot demo)"}

# Demo mix: newest posts plus health-knowledge, product and dealer-promotion posts.
DEMO_SOURCES = [
    ("latest", None, 3),
    ("kien-thuc-suc-khoe", 3, 4),
    ("aktiv-meno", 1011, 1),
    ("khuyen-mai", 4144, 1),
]


def _get(url: str):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def clean_text(raw_html: str) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw_html, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _to_post(p: dict, source: str) -> dict:
    media = (p.get("_embedded", {}).get("wp:featuredmedia") or [{}])[0]
    return {
        "id": p["id"],
        "source": source,
        "date": p["date"],
        "link": p["link"],
        "title": clean_text(p["title"]["rendered"]),
        "excerpt": clean_text(p["excerpt"]["rendered"]),
        "body": clean_text(p["content"]["rendered"])[:6000],
        "image_url": media.get("source_url"),
    }


def fetch_demo_posts() -> list[dict]:
    posts, seen = [], set()
    for source, cat, n in DEMO_SOURCES:
        url = f"{BASE}/wp-json/wp/v2/posts?per_page={n + 3}&_embed=wp:featuredmedia"
        if cat:
            url += f"&categories={cat}"
        picked = 0
        for p in _get(url):
            if p["id"] in seen or picked == n:
                continue
            seen.add(p["id"])
            posts.append(_to_post(p, source))
            picked += 1
    return posts


def fetch_products() -> list[str]:
    items = _get(f"{BASE}/wp-json/wc/store/v1/products?per_page=100")
    return sorted({clean_text(i["name"]) for i in items})
