"""Doppelherz content bot: website -> AI copy -> compliance -> approval -> schedule -> report.

  python run.py generate        fetch posts, draft with Claude, check rules, make pin images
  python run.py review          approve / reject drafts in the terminal (human gate)
  python run.py approve ID...   approve by post id (non-interactive)
  python run.py schedule        build the Facebook + Pinterest requests (dry run)
  python run.py status          print the queue

Flow:
  WP REST --> Claude writer --> code rules + Claude reviewer --> human --> FB/Pin requests --> report
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from bot import compliance, images, llm, prompts, publish, wp

ROOT = Path(__file__).parent
DATA = ROOT / "data"
QUEUE = DATA / "queue.json"
PRODUCTS = DATA / "products.json"


def load() -> list[dict]:
    return json.loads(QUEUE.read_text()) if QUEUE.exists() else []


def save(items: list[dict]) -> None:
    DATA.mkdir(exist_ok=True)
    QUEUE.write_text(json.dumps(items, ensure_ascii=False, indent=2))


def now() -> datetime:
    return datetime.now(publish.VN)


def process(post: dict, products: list[str]) -> dict:
    item = {"post": post, "log": [], "cost_usd": 0.0}
    gen, meta = llm.call_json(prompts.WRITER_SYSTEM, prompts.writer_user(post), prompts.WRITER_SCHEMA)
    item["generated"], item["cost_usd"] = gen, item["cost_usd"] + meta.get("cost_usd", 0)
    item["model"] = meta["model"]

    if gen["post_type"] == "promotion":
        item["status"] = "skipped"
        item["log"].append("Thông báo khuyến mại B2B cho đại lý: không đăng mạng xã hội.")
        return item

    rev, meta = llm.call_json(prompts.REVIEWER_SYSTEM, prompts.reviewer_user(post, gen), prompts.REVIEWER_SCHEMA)
    item["review"], item["cost_usd"] = rev, item["cost_usd"] + meta.get("cost_usd", 0)
    item["check"] = compliance.check(item, products)

    if item["check"]["verdict"] == "block" or rev["verdict"] == "block":
        item["status"] = "blocked"
    else:
        item["status"] = "pending_review"

    if post.get("image_url"):
        out = DATA / "images" / f"{post['id']}_pin.jpg"
        images.download_and_make_pin(post["image_url"], out, item["check"]["final"]["pin_title"])
        item["pin_image"] = str(out.relative_to(ROOT))
    item["generated_at"] = now().isoformat()
    return item


def cmd_generate() -> None:
    print("Đọc bài viết và sản phẩm từ doppelherz.vn ...")
    posts = wp.fetch_demo_posts()
    products = wp.fetch_products()
    PRODUCTS.parent.mkdir(exist_ok=True)
    PRODUCTS.write_text(json.dumps(products, ensure_ascii=False, indent=2))
    print(f"  {len(posts)} bài, {len(products)} sản phẩm. Gọi Claude ({llm.PROVIDER}, {llm.MODEL}) ...")

    def run(p):
        try:
            it = process(p, products)
        except Exception as e:  # one bad post must not stop the batch
            it = {"post": p, "status": "error", "log": [str(e)], "cost_usd": 0.0}
        print(f"  [{it['status']:>14}] {p['title'][:70]}")
        return it

    with ThreadPoolExecutor(max_workers=4) as pool:
        items = list(pool.map(run, posts))
    save(items)
    cmd_status()


def _show(it: dict) -> None:
    c = it["check"]
    print("\n" + "=" * 78)
    print(f"#{it['post']['id']}  {it['post']['title']}")
    print(f"Loại: {c['post_type']}  |  Kiểm tra code: {c['verdict']}  |  AI pháp chế: {it['review']['verdict']}")
    print("-" * 78 + "\nFACEBOOK:\n" + c["final"]["facebook_message"])
    print("-" * 78 + f"\nPINTEREST: {c['final']['pin_title']}\n{c['final']['pin_description']}")
    for i in c["issues"]:
        print(f"  ! [{i['level']}] {i['rule']}: \"{i['quote']}\"")
    for i in it["review"]["issues"]:
        print(f"  ! [AI] {i['problem']}: \"{i['quote']}\" -> {i['suggestion']}")


def cmd_review() -> None:
    items = load()
    for it in items:
        if it["status"] != "pending_review":
            continue
        _show(it)
        ans = input("\n[a] duyệt  [r] từ chối  [s] bỏ qua > ").strip().lower()
        if ans in ("a", "r"):
            it["status"] = "approved" if ans == "a" else "rejected"
            it["decided_at"] = now().isoformat()
            it["log"].append(f"Người duyệt: {it['status']}")
    save(items)
    cmd_status()


def cmd_approve(ids: list[str]) -> None:
    items = load()
    for it in items:
        if str(it["post"]["id"]) in ids and it["status"] == "pending_review":
            it["status"], it["decided_at"] = "approved", now().isoformat()
            it["log"].append("Người duyệt: approved")
    save(items)
    cmd_status()


def cmd_schedule() -> None:
    items = load()
    todo = [it for it in items if it["status"] == "approved"]
    t = now()
    fb_times = publish.next_slots(publish.FB_SLOTS, len(todo), t)
    pin_times = publish.next_slots(publish.PIN_SLOTS, len(todo), t)
    for it, ft, pt in zip(todo, fb_times, pin_times):
        it["requests"] = {"facebook": publish.fb_request(it, ft, t), "pinterest": publish.pin_request(it, pt)}
        it["status"] = "scheduled"
        it["log"].append(f"DRY RUN: Facebook {ft:%d/%m %H:%M}, Pinterest {pt:%d/%m %H:%M}")
        print(f"  #{it['post']['id']}  FB {ft:%d/%m %H:%M}  Pin {pt:%d/%m %H:%M}  {it['post']['title'][:50]}")
    save(items)
    cmd_status()


def cmd_status() -> None:
    items = load()
    counts: dict[str, int] = {}
    for it in items:
        counts[it["status"]] = counts.get(it["status"], 0) + 1
    cost = sum(it.get("cost_usd", 0) for it in items)
    print("\nHàng đợi:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())), f"| chi phí AI ≈ ${cost:.3f}")


if __name__ == "__main__":
    args = sys.argv[1:] or ["status"]
    {"generate": lambda: cmd_generate(), "review": lambda: cmd_review(),
     "approve": lambda: cmd_approve(args[1:]), "schedule": lambda: cmd_schedule(),
     "status": lambda: cmd_status()}[args[0]]()
