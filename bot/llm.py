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

MODEL = os.environ.get("BOT_MODEL", "claude-opus-5-5")
PROVIDER = os.environ.get("LLM_PROVIDER", "api" if os.environ.get("ANTHROPIC_API_KEY") else "claude-cli")


def call_json(system: str, user: str, schema: dict) -> tuple[dict, dict]:
    if PROVIDER == "api":
        return _call_api(system, user, schema)
    return _call_cli(system, user, schema)


def _call_cli(system: str, user: str, schema: dict) -> tuple[dict, dict]:
    cmd = [
        "claude", "-p", user,
        "--output-format", "json",
        "--json-schema", json.dumps(schema, ensure_ascii=False),
        "--model", MODEL,
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
    meta = {"provider": "claude-cli", "model": MODEL,
            "cost_usd": data.get("total_cost_usd", 0.0), "ms": data.get("duration_ms")}
    return data["structured_output"], meta


def _call_api(system: str, user: str, schema: dict) -> tuple[dict, dict]:
    import anthropic

    client = anthropic.Anthropic()
    resp = client.beta.messages.create(
        model=MODEL,
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
