"""Thin wrapper over claude-agent-sdk: one prompt in, validated structured output back.

Uses the machine's existing `claude` login (no API key). Every tool call passes through
guards.check via a PreToolUse hook.
"""
import json
from pathlib import Path

import anyio
from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, HookMatcher, ResultMessage, TextBlock,
                              ToolUseBlock, query)

from app import guards
from app.store import ROOT

PROMPTS = Path(__file__).parent / "prompts"
TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Bash", "WebFetch", "WebSearch", "Skill", "TodoWrite"]


class AgentError(Exception):
    pass


def prompt(name, **kw):
    return (PROMPTS / name).read_text(encoding="utf-8").format(**kw)


def _brief(block):
    inp = block.input or {}
    detail = inp.get("command") or inp.get("file_path") or inp.get("url") or inp.get("query") or inp.get("pattern") or ""
    return f"{block.name}: {str(detail)[:140]}"


LEAN_SYSTEM = "You classify and extract from the text you are given and return only the requested JSON."


async def _arun(text, *, model, schema, scratch, log, cancelled, max_turns, tools, lean):
    # lean: a pure text task with no tools, so skip the Claude Code system prompt, project files and thinking (10x faster).
    extra = {"system_prompt": LEAN_SYSTEM, "thinking": {"type": "disabled"}} if lean else {}
    opts = ClaudeAgentOptions(
        cwd=str(ROOT), model=model, tools=tools, allowed_tools=tools, **extra,
        setting_sources=[] if lean else ["project", "local"], permission_mode="bypassPermissions",
        hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[guards.hook(scratch)])]},
        max_turns=max_turns, add_dirs=[str(scratch)],
        env={"openout_any": "p", "openin_any": "p", "shell_escape": "f"},  # TeX paranoid file I/O
        output_format={"type": "json_schema", "schema": schema} if schema else None,
    )
    result = None
    async for msg in query(prompt=text, options=opts):
        if cancelled():
            raise AgentError("cancelled")
        if isinstance(msg, AssistantMessage):
            for b in msg.content:
                if isinstance(b, ToolUseBlock):
                    log("  · " + _brief(b))
        elif isinstance(msg, ResultMessage):
            result = msg
    if result is None or result.is_error:
        raise AgentError(f"agent failed: {getattr(result, 'subtype', 'no result')} {getattr(result, 'errors', '') or ''}".strip())
    if result.permission_denials:
        log(f"  · {len(result.permission_denials)} tool call(s) blocked by the safety guard")
    out = result.structured_output
    if schema and out is None:  # some models put the JSON in the text instead
        try:
            out = json.loads((result.result or "").strip().removeprefix("```json").removesuffix("```"))
        except json.JSONDecodeError as e:
            raise AgentError("agent returned no structured output") from e
    return out if schema else result.result


def run(text, *, model, schema=None, scratch, log=print, cancelled=lambda: False, max_turns=60, tools=TOOLS, lean=False):
    if lean and tools:
        raise ValueError("lean runs have no tools")
    return anyio.run(lambda: _arun(text, model=model, schema=schema, scratch=Path(scratch), log=log,
                                   cancelled=cancelled, max_turns=max_turns, tools=tools, lean=lean))


# ---------- output schemas ----------

TRIAGE = {"type": "object", "properties": {"keep": {"type": "array", "items": {"type": "string"}}}, "required": ["keep"]}

_SCORE = {"type": "integer", "minimum": 0, "maximum": 100}
SCORE = {"type": "object", "required": ["results"], "properties": {"results": {"type": "array", "items": {
    "type": "object", "required": ["key", "status"],
    "properties": {
        "key": {"type": "string"}, "status": {"enum": ["scored", "expired"]},
        "scores": {"type": "object", "properties": {k: _SCORE for k in ("technical", "experience", "behavioral", "career")},
                   "required": ["technical", "experience", "behavioral", "career"]},
        "location_verdict": {"enum": ["PASS", "FAIL", "FLAG"]}, "language_gate": {"enum": ["PASS", "FAIL", "FLAG"]},
        "language_note": {"type": ["string", "null"]}, "deadline": {"type": ["string", "null"]},
        "strengths": {"type": "array", "items": {"type": "string"}}, "gaps": {"type": "array", "items": {"type": "string"}},
        "language": {"type": "string"},
    }}}}}

DRAFT = {"type": "object", "required": ["status", "reason"], "properties": {
    "status": {"enum": ["READY", "EXPIRED", "VETO"]}, "reason": {"type": "string"},
    "apply_url": {"type": ["string", "null"]}, "deadline": {"type": ["string", "null"]},
    "form_notes": {"type": ["string", "null"]}, "fit_note": {"type": ["string", "null"]},
    "remote_note": {"type": ["string", "null"]}, "salary": {"type": ["string", "null"]},
    "fit_score": {"type": ["integer", "null"]}, "company": {"type": ["string", "null"]}, "title": {"type": ["string", "null"]},
}}

INTERVIEW = {"type": "object", "required": ["status", "path"], "properties": {"status": {"type": "string"}, "path": {"type": "string"}}}

REPLIES = {"type": "object", "required": ["results"], "properties": {"results": {"type": "array", "items": {
    "type": "object", "required": ["id", "signal", "application_id", "company", "role", "reason"],
    "properties": {
        "id": {"type": "string"},
        "signal": {"enum": ["ack", "assessment", "interview", "offer", "rejection", "other"]},
        "application_id": {"type": ["integer", "null"]},
        "company": {"type": ["string", "null"]}, "role": {"type": ["string", "null"]},
        "reason": {"type": ["string", "null"]},
    }}}}}

WHY_ROLE = {"type": "object", "required": ["answer"], "properties": {"answer": {"type": "string"}}}
