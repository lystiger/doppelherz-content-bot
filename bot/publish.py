"""Scheduling and the exact API requests the bot would send (dry run).

Facebook: Graph API v26.0, POST /{page_id}/photos with published=false and
scheduled_publish_time, which Meta accepts 10 minutes to 30 days ahead.
Pinterest: API v5, POST /v5/pins. With Trial access pins are sandbox-only, so
public pinning waits on Pinterest's Standard-access review.
"""
from datetime import datetime, timedelta, timezone

VN = timezone(timedelta(hours=7))
FB_SLOTS = [(11, 30), (20, 0)]
PIN_SLOTS = [(21, 0)]
FB_MIN, FB_MAX = timedelta(minutes=10), timedelta(days=30)


def next_slots(slots: list[tuple[int, int]], count: int, start: datetime) -> list[datetime]:
    out, day = [], start.astimezone(VN).date()
    while len(out) < count:
        for hh, mm in slots:
            t = datetime(day.year, day.month, day.day, hh, mm, tzinfo=VN)
            if t - start >= timedelta(hours=1) and len(out) < count:
                out.append(t)
        day += timedelta(days=1)
    return out


def fb_request(item: dict, when: datetime, now: datetime) -> dict:
    delta = when - now
    if not (FB_MIN <= delta <= FB_MAX):
        raise ValueError(f"scheduled_publish_time must be 10 min to 30 days ahead, got {delta}")
    return {
        "method": "POST",
        "url": "https://graph.facebook.com/v26.0/{PAGE_ID}/photos",
        "params": {
            "url": item["post"]["image_url"],
            "message": item["check"]["final"]["facebook_message"],
            "published": "false",
            "scheduled_publish_time": int(when.timestamp()),
            "access_token": "{PAGE_TOKEN}",
        },
    }


def pin_request(item: dict, when: datetime) -> dict:
    f = item["check"]["final"]
    return {
        "method": "POST",
        "url": "https://api.pinterest.com/v5/pins",
        "publish_at": when.isoformat(),
        "json": {
            "board_id": "{BOARD_ID}",
            "title": f["pin_title"],
            "description": f["pin_description"],
            "alt_text": f["alt_text"],
            "link": item["post"]["link"],
            "media_source": {"source_type": "image_base64", "content_type": "image/jpeg",
                             "data": f"<base64 of {item.get('pin_image', 'pin.jpg')}>"},
        },
    }
