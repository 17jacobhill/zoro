from pathlib import Path
import json
from datetime import datetime
from typing import Optional, List
from backend.plan_paths import get_existing_plan_markdown_path, get_plan_markdown_path

from backend.globals.schemas import (
    ChatsMetadataDB,
    ChatMetadata,
    PlanModel,
    Node,
    PlanEdge,
    HistoryEntry
)


ASSISTANT_DIR = Path.cwd() / ".zoro" / "generated" / "assistant"
METADATA_PATH = ASSISTANT_DIR / "metadata.json"


SUBSTEP_TRACKING_START = "\n\n<!-- zoro:substep-tracking:start -->\n"
SUBSTEP_TRACKING_END = "\n<!-- zoro:substep-tracking:end -->\n"


def _strip_substep_tracking_block(text: str) -> str:
    if not text:
        return ""
    start_idx = text.find(SUBSTEP_TRACKING_START)
    if start_idx == -1:
        return text
    end_idx = text.find(SUBSTEP_TRACKING_END, start_idx)
    if end_idx == -1:
        return text[:start_idx].rstrip()
    return (text[:start_idx] + text[end_idx + len(SUBSTEP_TRACKING_END):]).rstrip()


def _build_substep_tracking_block(step_id: str, substeps: list[dict]) -> str:
    lines = []
    lines.append("Substep tracking (required):")
    lines.append("Run this after finishing each substep so the frontend checkbox updates:")

    for s in substeps:
        sub_id = s.get("id")
        if not sub_id:
            continue
        lines.append(f"- After completing {sub_id}: zoro update-substep {step_id} {sub_id} completed")

    lines.append(f"(To undo: zoro update-substep {step_id} <substep-id> pending)")
    return SUBSTEP_TRACKING_START + "\n".join(lines) + SUBSTEP_TRACKING_END


def ensure_substep_tracking_instructions(plan: PlanModel) -> None:
    # Deprecated: tracking commands are now rendered inline under each substep
    # inside the **Substeps:** section (see plan_to_markdown).
    return


def plan_to_markdown(plan: PlanModel, chat_id: str) -> str:
    title = plan.nodes[0].title if plan.nodes else chat_id
    
    md = f"# Plan: {title} ({chat_id})\n\n"
    md += f"**Created:** {plan.created_at}\n"
    md += f"**Updated:** {plan.updated_at}\n\n"
    
    if plan.history:
        md += "<details><summary>📜 Plan History</summary>\n\n"
        for entry in plan.history:
            md += f"- **{entry.at}**: {entry.action}\n"
            if entry.details:
                md += f"  {entry.details}\n"
        md += "\n</details>\n\n"
    
    md += "---\n\n## Execution Steps\n\n"
    
    for node in plan.nodes:
        md += f"### {node.id}: [{node.type}] {node.title}\n\n"
        md += f"**Status:** {node.status}\n\n"
        
        if node.before_starting:
            md += "**Before Starting:**\n"
            md += f"{node.before_starting}\n\n"
        
        md += f"{node.description}\n\n"

        if node.type == "checking-with-user":
            md += "**Required artifacts (checking-with-user):**\n"
            md += "- User story (UI-visible flow)\n"
            md += "- Code story (Frontend → API → schema → persist to .zoro/generated/assistant/<chat-id>/plan.json → refresh)\n\n"
            md += "**Save after approval:**\n"
            md += f"- `zoro set-output {node.id} '<json of requirements_checklist + user_story + code_story>'`\n"
            md += f"- `zoro add-note {node.id} '<bullet summary of user_story + code_story (include persistence + refresh)>'`\n\n"
        
        if node.output:
            md += "**Output:**\n"
            md += f"```\n{node.output}\n```\n\n"
        
        if node.substeps:
            md += "**Substeps:**\n"
            for substep in node.substeps:
                check = "- \\[x\\]" if substep.get("completed") else "- \\[ \\]"
                substep_id = substep.get("id", "")
                id_text = f" ({substep_id})" if substep_id else ""
                md += f"{check}{id_text} {substep['text']}\n"

                # Inline tracking instruction directly under the substep it affects.
                if substep_id:
                    md += f"  - After completing {substep_id}: `zoro update-substep {node.id} {substep_id} completed`\n"
                    md += f"  - **⏸️ PAUSE HERE**: Call `attempt_completion` with result, wait for user approval before next substep\n"
            md += "\n"
        
        if node.rules:
            md += "**Rules to follow:**\n"
            for rule in node.rules:
                rule_type = rule.name.split(']')[0].replace('[', '') if '[' in rule.name else 'rule'
                md += f"- **[{rule_type}]** {rule.description}\n"
                md += f"  Reasoning: {rule.source}\n"
            md += "\n"
        
        if node.after_completing:
            md += "**After Completing:**\n"
            md += f"{node.after_completing}\n\n"
        
        if node.notes:
            md += "**Notes:**\n"
            for note in node.notes:
                note_text = (note or "").rstrip()
                # If the note already contains bullets, render it as-is for readability.
                lines = [ln for ln in note_text.splitlines() if ln.strip()]
                is_bullets = bool(lines) and all(ln.lstrip().startswith(('-', '*', '•')) for ln in lines)
                if is_bullets:
                    md += note_text + "\n"
                else:
                    md += f"- {note_text}\n"
            md += "\n"
        
        if node.audit:
            md += "<details><summary>📝 Audit Trail</summary>\n\n"
            for entry in node.audit:
                md += f"- **{entry.at}** ({entry.who}): {entry.action}\n"
                if entry.details:
                    md += f"  {entry.details}\n"
            md += "\n</details>\n\n"
        
        md += "---\n\n"
    
    return md


def get_chat_id_from_plan_md() -> Optional[str]:
    clinerules_path = get_existing_plan_markdown_path(Path.cwd())
    
    if not clinerules_path.exists():
        return None
    
    with open(clinerules_path, 'r', encoding='utf-8') as f:
        first_line = f.readline().strip()
    
    # First line format: "# Plan: {title} ({chat_id})"
    if '(' in first_line and ')' in first_line:
        start = first_line.rfind('(')
        end = first_line.rfind(')')
        if start != -1 and end != -1 and end > start:
            return first_line[start+1:end]
    
    return None


def load_metadata() -> ChatsMetadataDB:
    if not METADATA_PATH.exists():
        return ChatsMetadataDB()
    
    with open(METADATA_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return ChatsMetadataDB(**data)


def save_metadata(metadata: ChatsMetadataDB) -> None:
    ASSISTANT_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(METADATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(metadata.model_dump(), f, indent=2)


def load_plan(chat_id: str) -> Optional[PlanModel]:
    plan_path = ASSISTANT_DIR / chat_id / "plan.json"
    
    if not plan_path.exists():
        return None
    
    with open(plan_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return PlanModel(**data)


def save_plan(chat_id: str, plan: PlanModel) -> None:
    # Strip any legacy end-of-step tracking blocks so they don't linger in markdown.
    for node in plan.nodes:
        if node.after_completing:
            node.after_completing = _strip_substep_tracking_block(node.after_completing)

    ensure_substep_tracking_instructions(plan)

    plan_dir = ASSISTANT_DIR / chat_id
    plan_dir.mkdir(parents=True, exist_ok=True)
    
    plan_path = plan_dir / "plan.json"
    
    with open(plan_path, 'w', encoding='utf-8') as f:
        json.dump(plan.model_dump(by_alias=True), f, indent=2)
    
    clinerules_path = get_plan_markdown_path(Path.cwd())
    clinerules_path.parent.mkdir(parents=True, exist_ok=True)
    
    markdown = plan_to_markdown(plan, chat_id)
    with open(clinerules_path, 'w', encoding='utf-8') as f:
        f.write(markdown)


def merge_plan(chat_id: str, new_nodes: List[Node], new_edges: List[PlanEdge]) -> PlanModel:
    existing_plan = load_plan(chat_id)
    
    if not existing_plan:
        now = datetime.now().isoformat()
        existing_plan = PlanModel(
            created_at=now,
            updated_at=now,
            nodes=[],
            edges=[],
            history=[]
        )
    
    existing_node_ids = {node.id for node in existing_plan.nodes}
    
    for node in new_nodes:
        if node.id not in existing_node_ids:
            existing_plan.nodes.append(node)
    
    existing_edge_ids = {edge.id for edge in existing_plan.edges}
    
    for edge in new_edges:
        if edge.id not in existing_edge_ids:
            existing_plan.edges.append(edge)
    
    now = datetime.now().isoformat()
    existing_plan.updated_at = now
    
    existing_plan.history.append(
        HistoryEntry(
            at=now,
            action="merge",
            details=f"Added {len([n for n in new_nodes if n.id not in existing_node_ids])} nodes, {len([e for e in new_edges if e.id not in existing_edge_ids])} edges"
        )
    )
    
    save_plan(chat_id, existing_plan)
    
    return existing_plan
