"""Rules enforced in code, not left to the model.

Basis: Nghị định 15/2018/NĐ-CP Arts 26-27 (TPBVSK advertising), Luật Quảng cáo
amended by Luật 75/2025/QH15, Luật Trí tuệ nhân tạo 134/2025/QH15 (AI labels).
"""
import re

LABEL = "Thực phẩm bảo vệ sức khỏe"
WARNING = "Thực phẩm này không phải là thuốc, không có tác dụng thay thế thuốc chữa bệnh."

# Disease-treatment or absolute claims: a TPBVSK post must never contain them.
BLOCK_TERMS = [
    r"chữa (khỏi|bệnh|trị)", r"điều trị", r"khỏi bệnh", r"đặc trị", r"thay thế thuốc",
    r"thần dược", r"cam kết", r"100\s?%", r"tức thì", r"vĩnh viễn",
    r"bác sĩ khuyên dùng", r"được bác sĩ", r"tốt nhất", r"số 1",
]
# Softer phrasing a human must look at.
WARN_TERMS = [r"phòng ngừa", r"ngăn ngừa", r"phòng bệnh", r"tăng cường sức đề kháng", r"giảm nguy cơ"]

PIN_TITLE_MAX = 100
PIN_DESC_MAX = 500
ALT_MAX = 500


def _find(patterns: list[str], text: str) -> list[str]:
    hits = []
    for p in patterns:
        hits += [m.group(0) for m in re.finditer(p, text, flags=re.I)]
    return hits


def mentions_product(text: str, products: list[str]) -> list[str]:
    low = text.lower()
    return [p for p in products if p.lower() in low]


def check(item: dict, products: list[str]) -> dict:
    """Return a rule report and the final, code-stamped copy for one item."""
    gen = item["generated"]
    fb = gen["facebook"]["message"]
    pin = gen["pinterest"]
    all_text = " ".join([fb, pin["title"], pin["description"], pin["alt_text"]])

    issues = []
    for hit in _find(BLOCK_TERMS, all_text):
        issues.append({"level": "block", "rule": "Cấm tuyên bố chữa bệnh / tuyệt đối hóa", "quote": hit})
    for hit in _find(WARN_TERMS, all_text):
        issues.append({"level": "warn", "rule": "Tuyên bố công dụng cần đối chiếu hồ sơ xác nhận", "quote": hit})

    # Code overrides the model: naming a product makes it an advertisement.
    named = mentions_product(all_text + " " + item["post"]["title"], products)
    post_type = gen["post_type"]
    if named and post_type == "education":
        post_type = "product_ad"
        issues.append({"level": "warn", "rule": "Bài có nhắc sản phẩm nên được xếp là quảng cáo", "quote": ", ".join(named[:3])})

    if post_type == "product_ad":
        issues.append({"level": "block", "rule": "Chưa có số xác nhận nội dung quảng cáo (Cục ATTP) trong thư viện",
                       "quote": ", ".join(named[:3]) or "sản phẩm"})

    final_fb = fb.strip()
    if post_type == "product_ad":
        final_fb += f"\n\n{LABEL}. {WARNING}"
    final_fb += "\n\n#Doppelherz\nNội dung có sự hỗ trợ của AI."

    if len(pin["title"]) > PIN_TITLE_MAX:
        issues.append({"level": "fix", "rule": f"Tiêu đề Pinterest > {PIN_TITLE_MAX} ký tự, đã cắt", "quote": pin["title"][:40]})
    if len(pin["description"]) > PIN_DESC_MAX:
        issues.append({"level": "fix", "rule": f"Mô tả Pinterest > {PIN_DESC_MAX} ký tự, đã cắt", "quote": pin["description"][:40]})

    final = {
        "facebook_message": final_fb,
        "pin_title": pin["title"][:PIN_TITLE_MAX],
        "pin_description": pin["description"][:PIN_DESC_MAX],
        "alt_text": pin["alt_text"][:ALT_MAX],
    }
    levels = {i["level"] for i in issues}
    verdict = "block" if "block" in levels else ("review" if "warn" in levels else "pass")
    return {"post_type": post_type, "products": named, "issues": issues, "verdict": verdict, "final": final}
