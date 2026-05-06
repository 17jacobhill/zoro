from __future__ import annotations

import re

import click

from backend.visualization.paths import get_notes_path, get_plan_path
from backend.visualization.services.notes_store import append_note_record
from backend.visualization.services.plan_tracker import get_chat_id_from_plan_md, load_plan_data, find_item_by_id


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
@click.option('--chat-id', default=None, help='Chat ID (auto-detect from .zoro/CURRENT_PLAN.md if not provided)')
def add_note(step_id, note, chat_id):
    if not chat_id:
        chat_id = get_chat_id_from_plan_md()

    if not chat_id:
        click.echo("❌ No active visualization plan found")
        return

    plan_path = get_plan_path(chat_id)
    notes_path = get_notes_path(chat_id)
    click.echo(f"📍 Chat ID: {chat_id}")
    click.echo(f"📄 Updating: {plan_path}")
    click.echo(f"🗒️ Saving notes in: {notes_path}")

    plan_data = load_plan_data(chat_id)
    if not plan_data:
        click.echo(f"❌ No plan found for chat: {chat_id}")
        return

    item = find_item_by_id(plan_data.get("plan", {}).get("items", []), step_id)
    if not item:
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

        click.echo("ℹ️  Note wasn't in bullet format; saving normalized bullet version.")
        note_to_save = suggested

    append_note_record(
        chat_id,
        note_text=note_to_save,
        source="plan-item-note",
        plan_item_id=step_id,
        explanation=f"CLI note attached to plan item {step_id}",
    )
    
    click.echo(f"✅ Added note to {step_id}")
