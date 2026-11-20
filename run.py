"""Doppelherz content bot: website -> AI copy -> compliance -> approval -> schedule -> report.

  python run.py generate        fetch posts, draft with Claude, check rules, make pin images
  python run.py review          approve / reject drafts in the terminal (human gate)
  python run.py approve ID...   approve by post id (non-interactive)
  python run.py reject ID "reason"  reject with a reason; Claude redrafts it (non-interactive)
  python run.py redraft         rewrite rejected drafts using the reviewer's reason
  python run.py schedule        build the Facebook + Pinterest requests (dry run)
  python run.py status          print the queue

Flow:
  WP REST --> Claude writer --> code rules + Claude reviewer --> human --> FB/Pin requests --> report
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from bot import compliance, images, llm, prompts, publish, wp

MAX_REDRAFTS = 2  # a third rejection drops the post

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


def process(post: dict, products: list[str], previous: dict | None = None, feedback: str | None = None) -> dict:
    item = {"post": post, "log": [], "cost_usd": 0.0}
    user = prompts.redraft_user(post, previous, feedback) if feedback else prompts.writer_user(post)
    gen, meta = llm.call_json(prompts.WRITER_SYSTEM, user, prompts.WRITER_SCHEMA, llm.WRITER_MODEL)
    item["generated"], item["cost_usd"] = gen, item["cost_usd"] + meta.get("cost_usd", 0)
    item["model"] = meta["model"]

    if gen["post_type"] == "promotion":
        item["status"] = "skipped"
        item["log"].append("Thông báo khuyến mại B2B cho đại lý: không đăng mạng xã hội.")
        return item

    rev, meta = llm.call_json(prompts.REVIEWER_SYSTEM, prompts.reviewer_user(post, gen), prompts.REVIEWER_SCHEMA, llm.REVIEWER_MODEL)
    item["review"], item["cost_usd"] = rev, item["cost_usd"] + meta.get("cost_usd", 0)
    item["review_model"] = meta["model"]
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
    # Merge by post id: keep every decision already made; only new posts and
    # posts that failed last time go to Claude. Re-running never duplicates work.
    items = load()
    known = {it["post"]["id"]: it for it in items}
    todo = [p for p in posts if p["id"] not in known or known[p["id"]]["status"] == "error"]
    print(f"  {len(posts)} bài, {len(products)} sản phẩm; {len(todo)} bài mới hoặc lỗi lần trước. "
          f"Gọi Claude ({llm.PROVIDER}, viết: {llm.WRITER_MODEL}, kiểm tra: {llm.REVIEWER_MODEL}) ...")

    def run(p):
        try:
            it = process(p, products)
        except Exception as e:  # one bad post must not stop the batch
            it = {"post": p, "status": "error", "log": [f"Lỗi sau 3 lần thử: {e}"], "cost_usd": 0.0}
        print(f"  [{it['status']:>14}] {p['title'][:70]}")
        return it

    with ThreadPoolExecutor(max_workers=4) as pool:
        fresh = {it["post"]["id"]: it for it in pool.map(run, todo)}
    items = [fresh.pop(it["post"]["id"], it) for it in items] + list(fresh.values())
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
        if ans == "a":
            it["status"], it["decided_at"] = "approved", now().isoformat()
            it["log"].append("Người duyệt: approved")
        elif ans == "r":
            _reject(it, input("Lý do từ chối (Claude sẽ viết lại theo lý do này) > ").strip())
    save(items)
    cmd_status()


def _reject(it: dict, reason: str) -> None:
    """A rejection with a reason sends the post back to Claude, up to MAX_REDRAFTS times."""
    it["decided_at"] = now().isoformat()
    it.setdefault("feedback", []).append(reason or "Không ghi lý do")
    if len(it["feedback"]) > MAX_REDRAFTS:
        it["status"] = "dropped"
        it["log"].append(f"Người duyệt từ chối lần {len(it['feedback'])}: loại bài. Lý do: {reason}")
    else:
        it["status"] = "needs_redraft"
        it["log"].append(f"Người duyệt từ chối lần {len(it['feedback'])}, chờ viết lại. Lý do: {reason}")


def cmd_reject(post_id: str, reason: str) -> None:
    items = load()
    for it in items:
        if str(it["post"]["id"]) == post_id and it["status"] == "pending_review":
            _reject(it, reason)
    save(items)
    cmd_status()


def cmd_redraft() -> None:
    """Rewrite each rejected draft with the reviewer's reason, then send it back to review."""
    items = load()
    products = json.loads(PRODUCTS.read_text())
    todo = [it for it in items if it["status"] == "needs_redraft"]
    print(f"Viết lại {len(todo)} bài bị từ chối ...")

    def run(old):
        try:
            new = process(old["post"], products, previous=old["generated"], feedback=old["feedback"][-1])
        except Exception as e:
            old["log"].append(f"Viết lại lỗi sau 3 lần thử, giữ chờ viết lại: {e}")
            return old
        new["feedback"] = old["feedback"]
        new["cost_usd"] += old.get("cost_usd", 0)
        new["log"] = old["log"] + [f"Claude viết lại lần {len(old['feedback'])} theo lý do từ chối"] + new["log"]
        print(f"  [{new['status']:>14}] {old['post']['title'][:70]}")
        return new

    with ThreadPoolExecutor(max_workers=4) as pool:
        done = {it["post"]["id"]: it for it in pool.map(run, todo)}
    items = [done.get(it["post"]["id"], it) for it in items]
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


def cmd_recheck() -> None:
    """Re-run the code rules on saved drafts (no AI calls), e.g. after a rule change."""
    products = [re.sub(r"^TPBVSK\s+", "", p, flags=re.I) for p in json.loads(PRODUCTS.read_text())]
    PRODUCTS.write_text(json.dumps(products, ensure_ascii=False, indent=2))
    items = load()
    for it in items:
        if "check" not in it:
            continue
        it["check"] = compliance.check(it, products)
        if (it["check"]["verdict"] == "block" or it["review"]["verdict"] == "block") and it["status"] != "blocked":
            it["status"] = "blocked"
            it.pop("requests", None)
            it["log"].append("Kiểm tra lại: bị chặn theo luật mới")
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
     "reject": lambda: cmd_reject(args[1], " ".join(args[2:])), "redraft": lambda: cmd_redraft(),
     "recheck": lambda: cmd_recheck(), "status": lambda: cmd_status()}[args[0]]()
