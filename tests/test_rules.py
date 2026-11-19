from datetime import datetime, timedelta

import pytest
from PIL import Image

from bot import compliance, images, publish

PRODUCTS = ["Aktiv Meno", "Kinder Optima"]


def item(fb, title="Bài viết", post_type="education"):
    return {
        "post": {"title": title, "image_url": "https://x/y.jpg", "link": "https://doppelherz.vn/a"},
        "generated": {
            "post_type": post_type,
            "facebook": {"message": fb},
            "pinterest": {"title": "T" * 120, "description": "Mô tả", "alt_text": "Ảnh"},
        },
    }


def test_clean_education_passes_without_warning_text():
    r = compliance.check(item("Mẹo ăn uống lành mạnh mùa đông."), PRODUCTS)
    assert r["verdict"] == "pass"
    assert compliance.WARNING not in r["final"]["facebook_message"]
    assert "Nội dung có sự hỗ trợ của AI." in r["final"]["facebook_message"]


def test_cure_claim_is_blocked():
    r = compliance.check(item("Sản phẩm giúp chữa khỏi mất ngủ."), PRODUCTS)
    assert r["verdict"] == "block"


def test_product_name_turns_education_into_ad_with_label_and_warning():
    r = compliance.check(item("Aktiv Meno đồng hành cùng phụ nữ tuổi 45."), PRODUCTS)
    assert r["post_type"] == "product_ad"
    assert r["verdict"] == "block"  # no confirmed ad dossier in the library yet
    assert compliance.LABEL in r["final"]["facebook_message"]
    assert compliance.WARNING in r["final"]["facebook_message"]


def test_product_ad_quotes_the_detected_product():
    r = compliance.check(item("Tham khảo Aktiv Meno nhé.", post_type="product_ad"), PRODUCTS)
    blocks = [i for i in r["issues"] if i["level"] == "block"]
    assert any("Aktiv Meno" in i["quote"] for i in blocks)


def test_soft_claim_needs_human_review():
    r = compliance.check(item("Vitamin D giúp tăng cường sức đề kháng."), PRODUCTS)
    assert r["verdict"] == "review"


def test_pin_title_truncated_to_100():
    r = compliance.check(item("Ok."), PRODUCTS)
    assert len(r["final"]["pin_title"]) == 100


def test_pin_image_is_2_by_3():
    out = images.make_pin_image(Image.new("RGB", (1200, 630), "red"))
    assert out.size == (1000, 1500)


def test_fb_schedule_window_enforced():
    now = datetime.now(publish.VN)
    it = {"post": {"image_url": "u"}, "check": {"final": {"facebook_message": "m"}}}
    assert publish.fb_request(it, now + timedelta(hours=2), now)["params"]["published"] == "false"
    with pytest.raises(ValueError):
        publish.fb_request(it, now + timedelta(days=31), now)


def test_slots_at_least_one_hour_ahead():
    now = datetime.now(publish.VN)
    for t in publish.next_slots(publish.FB_SLOTS, 5, now):
        assert t - now >= timedelta(hours=1)
