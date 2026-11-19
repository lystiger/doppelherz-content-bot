"""Build the static demo page (site/index.html) from data/queue.json.

Static on purpose: the link keeps working when the reviewer opens it days later
and the PC that ran the bot is off.
"""
import io
import json
import shutil
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
ASSETS = SITE / "assets"


def save_source_image(url: str, out: Path) -> None:
    if out.exists():
        return
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        img = Image.open(io.BytesIO(r.read())).convert("RGB")
    img.thumbnail((1200, 1200))
    img.save(out, "JPEG", quality=82)


def slim(it: dict) -> dict:
    p = it["post"]
    out = {
        "id": p["id"], "title": p["title"], "link": p["link"], "date": p["date"][:10],
        "status": it["status"], "log": it.get("log", []), "cost": round(it.get("cost_usd", 0), 4),
    }
    if p.get("image_url"):
        src = ASSETS / "src" / f"{p['id']}.jpg"
        save_source_image(p["image_url"], src)
        out["src_img"] = str(src.relative_to(SITE))
    gen = it.get("generated")
    if gen:
        out["type"] = gen["post_type"]
        out["type_reason"] = gen["type_reason"]
    if "check" in it:
        c = it["check"]
        out.update({
            "type": c["post_type"], "code_verdict": c["verdict"], "issues": c["issues"],
            "fb": c["final"]["facebook_message"], "pin_title": c["final"]["pin_title"],
            "pin_desc": c["final"]["pin_description"], "alt": c["final"]["alt_text"],
            "ai_verdict": it["review"]["verdict"], "ai_issues": it["review"]["issues"],
        })
    if it.get("pin_image"):
        dst = ASSETS / "pins" / Path(it["pin_image"]).name
        shutil.copy(ROOT / it["pin_image"], dst)
        out["pin_img"] = str(dst.relative_to(SITE))
    if it.get("requests"):
        r = json.loads(json.dumps(it["requests"]))
        out["fb_time"] = r["facebook"]["params"]["scheduled_publish_time"]
        out["pin_time"] = r["pinterest"]["publish_at"]
        out["requests"] = r
    return out


def main() -> None:
    (ASSETS / "src").mkdir(parents=True, exist_ok=True)
    (ASSETS / "pins").mkdir(parents=True, exist_ok=True)
    items = json.loads((ROOT / "data" / "queue.json").read_text())
    products = json.loads((ROOT / "data" / "products.json").read_text())
    data = {
        "items": [slim(it) for it in items],
        "products": len(products),
        "model": next((it["model"] for it in items if it.get("model")), ""),
        "generated_at": max((it.get("generated_at", "") for it in items), default=""),
    }
    tpl = (SITE / "template.html").read_text()
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    (SITE / "index.html").write_text(tpl.replace("__DATA__", payload))
    print(f"site/index.html: {len(data['items'])} items")


if __name__ == "__main__":
    main()
