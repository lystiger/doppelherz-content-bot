"""One function, call_json(), returning schema-valid JSON from Claude.

Two providers:
- claude-cli (default): headless Claude Code (`claude -p`), uses the logged-in
  subscription, so the demo needs no API key. Hooks and settings are disabled
  so local agent config cannot leak into generated copy.
- api: Anthropic SDK with ANTHROPIC_API_KEY, for production.
"""
import json
import os
import subprocess
import tempfile

from bot.retry import with_retry

MODEL = os.environ.get("BOT_MODEL", "claude-opus-5-5")
# Writer and legal checker can run on different models (e.g. Haiku writes, Sonnet checks).
WRITER_MODEL = os.environ.get("BOT_WRITER_MODEL", MODEL)
REVIEWER_MODEL = os.environ.get("BOT_REVIEWER_MODEL", MODEL)
PROVIDER = os.environ.get("LLM_PROVIDER", "api" if os.environ.get("ANTHROPIC_API_KEY") else "claude-cli")


def call_json(system: str, user: str, schema: dict, model: str = MODEL) -> tuple[dict, dict]:
    """Up to 3 attempts; the last error is raised to the caller."""
    return with_retry(_call_api if PROVIDER == "api" else _call_cli, system, user, schema, model)


def _call_cli(system: str, user: str, schema: dict, model: str) -> tuple[dict, dict]:
    cmd = [
        "claude", "-p", user,
        "--output-format", "json",
        "--json-schema", json.dumps(schema, ensure_ascii=False),
        "--model", model,
        "--system-prompt", system,
        "--tools", "",
        "--settings", '{"disableAllHooks":true}',
        "--setting-sources", "",
        "--no-session-persistence",
    ]
    with tempfile.TemporaryDirectory() as tmp:
        out = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=300)
    if out.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {out.stderr.strip() or out.stdout[:500]}")
    data = json.loads(out.stdout)
    if data.get("is_error") or data.get("structured_output") is None:
        raise RuntimeError(f"claude CLI returned no structured output: {data.get('result', '')[:500]}")
    meta = {"provider": "claude-cli", "model": model,
            "cost_usd": data.get("total_cost_usd", 0.0), "ms": data.get("duration_ms")}
    return data["structured_output"], meta


def _call_api(system: str, user: str, schema: dict, model: str) -> tuple[dict, dict]:
    import anthropic

    client = anthropic.Anthropic()
    resp = client.beta.messages.create(
        model=model,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("model declined the request")
    text = next(b.text for b in resp.content if b.type == "text")
    meta = {"provider": "api", "model": resp.model,
            "input_tokens": resp.usage.input_tokens, "output_tokens": resp.usage.output_tokens}
    return json.loads(text), meta
