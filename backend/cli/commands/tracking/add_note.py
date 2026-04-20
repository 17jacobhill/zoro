from __future__ import annotations

import re
from datetime import datetime

import click

from backend.assistant.plan_manager import load_plan, save_plan
from backend.cli.utils import detect_active_chat
from backend.globals.schemas import AuditEntry


_BULLET_PREFIX_RE = re.compile(r"^(?:-|\*|•)\s+")


def _looks_like_bullets(text: str) -> bool:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return False
    return all(bool(_BULLET_PREFIX_RE.match(ln)) for ln in lines)


def _normalize_bullets(text: str) -> str:
    out_lines: list[str] = []
    for raw in (text or "").splitlines():
        ln = raw.strip()
        if not ln:
            continue
        if ln.startswith("•"):
            ln = "- " + ln[1:].lstrip()
        elif ln.startswith("*"):
            ln = "- " + ln[1:].lstrip()
        elif ln.startswith("-") and not ln.startswith("- "):
            ln = "- " + ln[1:].lstrip()
        out_lines.append(ln)
    return "\n".join(out_lines)


def _bulletize_free_text(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    # Light cleanup for common prefixes.
    prefixes = [
        "ui behavior decision:",
        "ui decision:",
        "behavior decision:",
        "decision:",
        "note:",
    ]
    lowered = cleaned.lower()
    for p in prefixes:
        if lowered.startswith(p):
            cleaned = cleaned[len(p):].lstrip()
            break

    # Split into bullet-ish clauses.
    # Keep this deterministic and conservative (no LLM):
    # - periods / semicolons / newlines
    # - some connectors like "Also" / "+".
    normalized = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\n", ". ")
    normalized = normalized.replace(";", ". ")
    normalized = normalized.replace(" + ", ". ")
    normalized = re.sub(r"\s+", " ", normalized).strip()

    parts = [p.strip() for p in re.split(r"\.\s+", normalized) if p.strip()]
    # Handle a leading "Also ..." as its own bullet.
    bullets: list[str] = []
    for part in parts:
        if part.lower().startswith("also "):
            part = part[5:].strip()
        if not part:
            continue
        bullets.append(f"- {part}")

    return "\n".join(bullets)


@click.command()
@click.argument('step_id')
@click.argument('note')
@click.option('--chat-id', default=None, help='Chat ID (auto-detect from .clinerules if not provided)')
def add_note(step_id, note, chat_id):
    if not chat_id:
        chat_id = detect_active_chat()
    
    plan_path = f".zoro/generated/assistant/{chat_id}/plan.json"
    click.echo(f"📍 Chat ID: {chat_id}")
    click.echo(f"📄 Updating: {plan_path}")
    
    plan = load_plan(chat_id)
    if not plan:
        click.echo(f"❌ No plan found for chat: {chat_id}")
        return
    
    node = next((n for n in plan.nodes if n.id == step_id), None)
    if not node:
        click.echo(f"❌ Step {step_id} not found")
        return

    original_note = (note or "").strip()
    if not original_note:
        click.echo("❌ Note is empty")
        return

    note_to_save: str
    if _looks_like_bullets(original_note):
        note_to_save = _normalize_bullets(original_note)
    else:
        suggested = _bulletize_free_text(original_note)
        if not suggested:
            click.echo("❌ Could not format note")
            return

        click.echo("⚠️  Note isn't in bullet format.")
        click.echo("\nSuggested bullet version:\n")
        click.echo(suggested)

        proceed = click.confirm("\nSave the suggested bullet version?", default=True)
        if not proceed:
            click.echo("⊗ Cancelled (note not saved)")
            return

        note_to_save = suggested

    # Add to notes array
    node.notes.append(note_to_save)
    
    # Log in audit trail
    node.audit.append(AuditEntry(
        at=datetime.now().isoformat(),
        who="ai",
        action="note_added",
        details=note_to_save
    ))
    
    save_plan(chat_id, plan)
    
    click.echo(f"✅ Added note to {step_id}")
