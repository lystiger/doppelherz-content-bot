"""Retry with backoff for calls to outside services (Claude, the website, Facebook, Pinterest).

The demo waits a few seconds between attempts; production would wait minutes
(1, 5, 15) and alert someone after the last failure.
"""
import time

DELAYS = (2, 5)  # seconds before attempt 2 and attempt 3


def with_retry(fn, *args, delays=DELAYS, **kwargs):
    for wait in (*delays, None):
        try:
            return fn(*args, **kwargs)
        except Exception:
            if wait is None:
                raise
            time.sleep(wait)
