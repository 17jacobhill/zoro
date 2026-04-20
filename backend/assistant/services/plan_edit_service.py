from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from backend.assistant.plan_manager import load_plan, save_plan
from backend.globals.schemas import AuditEntry, PlanEdge, RuleRef


class PlanEditError(RuntimeError):
    pass


def _require_plan(chat_id: str):
    plan = load_plan(chat_id)
    if not plan:
        raise PlanEditError("Plan not found")
    return plan


def _require_node(plan, node_id: str):
    node = next((n for n in plan.nodes if n.id == node_id), None)
    if not node:
        raise PlanEditError("Node not found")
    return node


def add_substep(
    *,
    chat_id: str,
    node_id: str,
    text: str,
    requested_id: Optional[str] = None,
    who: str = "user",
) -> dict[str, Any]:
    plan = _require_plan(chat_id)
    node = _require_node(plan, node_id)

    text = (text or "").strip()
    requested_id = (requested_id or "").strip() or None

    if not text:
        raise PlanEditError("Missing text")
    if node.type != "code-style":
        raise PlanEditError("Substeps only supported for code-style nodes")

    if node.substeps is None:
        node.substeps = []

    existing_ids = {s.get("id") for s in node.substeps if isinstance(s, dict)}

    substep_id = requested_id
    if not substep_id:
        n = 1
        while f"substep-{n}" in existing_ids:
            n += 1
        substep_id = f"substep-{n}"
    elif substep_id in existing_ids:
        raise PlanEditError(f"Substep id already exists: {substep_id}")

    node.substeps.append({"id": substep_id, "text": text, "completed": False})
    node.audit.append(
        AuditEntry(
            at=datetime.now().isoformat(),
            who=who,
            action="substep_added",
            details=f"{substep_id}: {text}",
        )
    )

    plan.updated_at = datetime.now().isoformat()
    save_plan(chat_id, plan)
    return {"node": node.model_dump(by_alias=True)}


def delete_substep(*, chat_id: str, node_id: str, substep_id: str, who: str = "user") -> dict[str, Any]:
    plan = _require_plan(chat_id)
    node = _require_node(plan, node_id)

    if not node.substeps:
        raise PlanEditError("No substeps on node")

    before = len(node.substeps)
    removed = [s for s in node.substeps if isinstance(s, dict) and s.get("id") == substep_id]
    node.substeps = [s for s in node.substeps if not (isinstance(s, dict) and s.get("id") == substep_id)]
    if len(node.substeps) == before:
        raise PlanEditError("Substep not found")

    removed_text = removed[0].get("text", "") if removed else ""
    node.audit.append(
        AuditEntry(
            at=datetime.now().isoformat(),
            who=who,
            action="substep_deleted",
            details=f"{substep_id}: {removed_text}",
        )
    )

    plan.updated_at = datetime.now().isoformat()
    save_plan(chat_id, plan)
    return {"node": node.model_dump(by_alias=True)}


def add_rule(
    *,
    chat_id: str,
    node_id: str,
    rule_id: Optional[str],
    name: str,
    description: str,
    source: str,
    who: str = "user",
) -> dict[str, Any]:
    plan = _require_plan(chat_id)
    node = _require_node(plan, node_id)

    rule_id = (rule_id or "").strip() or str(uuid.uuid4())
    name = (name or "").strip()
    description = (description or "").strip()
    source = (source or "").strip()

    if not name:
        raise PlanEditError("Missing name")
    if not description:
        raise PlanEditError("Missing description")
    if not source:
        raise PlanEditError("Missing source")

    existing_ids = {r.rule_id for r in (node.rules or [])}
    if rule_id in existing_ids:
        raise PlanEditError(f"Rule id already exists on node: {rule_id}")

    node.rules.append(RuleRef(rule_id=rule_id, name=name, description=description, source=source))
    node.audit.append(
        AuditEntry(
            at=datetime.now().isoformat(),
            who=who,
            action="rule_added",
            details=f"{rule_id}: {name}",
        )
    )

    plan.updated_at = datetime.now().isoformat()
    save_plan(chat_id, plan)
    return {"node": node.model_dump(by_alias=True)}


def delete_rule(*, chat_id: str, node_id: str, rule_id: str) -> dict[str, Any]:
    plan = _require_plan(chat_id)
    node = _require_node(plan, node_id)

    original_count = len(node.rules or [])
    node.rules = [r for r in (node.rules or []) if r.rule_id != rule_id]
    if len(node.rules) == original_count:
        raise PlanEditError("Rule not found")

    plan.updated_at = datetime.now().isoformat()
    save_plan(chat_id, plan)
    return {"node_id": node_id, "rule_id": rule_id}


def delete_node(*, chat_id: str, node_id: str) -> dict[str, Any]:
    plan = _require_plan(chat_id)

    node_to_delete = next((n for n in plan.nodes if n.id == node_id), None)
    if not node_to_delete:
        raise PlanEditError("Node not found")

    predecessors = [e.from_node for e in plan.edges if e.to_node == node_id]
    successors = [e.to_node for e in plan.edges if e.from_node == node_id]

    plan.nodes = [n for n in plan.nodes if n.id != node_id]
    plan.edges = [e for e in plan.edges if e.from_node != node_id and e.to_node != node_id]

    for pred in predecessors:
        for succ in successors:
            plan.edges.append(
                PlanEdge(
                    id=f"edge-{str(uuid.uuid4())[:8]}",
                    from_node=pred,
                    to_node=succ,
                    type="sequence",
                )
            )

    plan.updated_at = datetime.now().isoformat()
    save_plan(chat_id, plan)

    return {
        "node_id": node_id,
        "edges_removed": len(predecessors) + len(successors),
        "edges_added": len(predecessors) * len(successors),
    }


def append_audit(
    *,
    chat_id: str,
    node_id: str,
    action: str,
    details: str,
    who: str = "user",
) -> dict[str, Any]:
    plan = _require_plan(chat_id)
    node = _require_node(plan, node_id)

    action = (action or "").strip()
    if not action:
        raise PlanEditError("Missing action")

    node.audit.append(
        AuditEntry(
            at=datetime.now().isoformat(),
            who=(who or "user").strip() or "user",
            action=action,
            details=(details or "").strip(),
        )
    )

    plan.updated_at = datetime.now().isoformat()
    save_plan(chat_id, plan)
    return {"node": node.model_dump(by_alias=True)}

