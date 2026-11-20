"""Queue merge, reject -> redraft loop and retry. No Claude calls: process() is stubbed."""
import json

import pytest

import run
from bot import retry


@pytest.fixture
def queue(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "DATA", tmp_path)
    monkeypatch.setattr(run, "QUEUE", tmp_path / "queue.json")
    monkeypatch.setattr(run, "PRODUCTS", tmp_path / "products.json")
    (tmp_path / "products.json").write_text("[]")
    calls = []

    def fake_process(post, products, previous=None, feedback=None):
        calls.append((post["id"], feedback))
        return {"post": post, "status": "pending_review", "log": [], "cost_usd": 0.1,
                "generated": {"facebook": {"message": f"v{len(calls)}"}, "pinterest": {"title": "t"}}}

    monkeypatch.setattr(run, "process", fake_process)
    return calls


def post(i):
    return {"id": i, "title": f"Bài {i}"}


def test_generate_keeps_decisions_and_retries_only_errors(queue, monkeypatch):
    run.save([{"post": post(1), "status": "approved", "log": [], "cost_usd": 0},
              {"post": post(2), "status": "error", "log": [], "cost_usd": 0}])
    monkeypatch.setattr(run.wp, "fetch_demo_posts", lambda: [post(1), post(2), post(3)])
    monkeypatch.setattr(run.wp, "fetch_products", lambda: [])
    run.cmd_generate()
    items = {it["post"]["id"]: it["status"] for it in run.load()}
    assert items == {1: "approved", 2: "pending_review", 3: "pending_review"}
    assert sorted(i for i, _ in queue) == [2, 3]  # the approved post was not sent to Claude again


def test_reject_redraft_then_drop(queue):
    run.save([{"post": post(7), "status": "pending_review", "log": [], "cost_usd": 0,
               "generated": {"facebook": {"message": "v0"}, "pinterest": {"title": "t"}}}])
    for n in (1, 2):
        run.cmd_reject("7", f"lý do {n}")
        assert run.load()[0]["status"] == "needs_redraft"
        run.cmd_redraft()
        it = run.load()[0]
        assert it["status"] == "pending_review"
        assert queue[-1] == (7, f"lý do {n}")  # Claude got the reviewer's reason
    run.cmd_reject("7", "lý do 3")
    it = run.load()[0]
    assert it["status"] == "dropped" and len(it["feedback"]) == 3
    assert len(queue) == 2  # no third redraft


def test_retry_succeeds_on_third_attempt_and_gives_up_after():
    tries = []

    def flaky():
        tries.append(1)
        if len(tries) < 3:
            raise RuntimeError("down")
        return "ok"

    assert retry.with_retry(flaky, delays=(0, 0)) == "ok" and len(tries) == 3

    def broken():
        raise RuntimeError("still down")

    with pytest.raises(RuntimeError, match="still down"):
        retry.with_retry(broken, delays=(0, 0))
