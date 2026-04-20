from __future__ import annotations
from pathlib import Path
import json
from typing import Optional, List
from datetime import datetime

from backend.globals.schemas import (
    EnforcementV2DB,
    EnforcementRecordV2,
    Requirement,
    RequirementVerification,
    RequirementTest,
    FileSummary,
    CodeBlock,
)


def _get_enforcement_v2_path(chat_id: str) -> Path:
    return Path.cwd() / ".zoro" / "generated" / "assistant" / chat_id / "enforcement_v2.json"


def load_enforcement_v2(chat_id: str) -> EnforcementV2DB:
    path = _get_enforcement_v2_path(chat_id)
    if not path.exists():
        return EnforcementV2DB(version="2.0", records=[])
    
    if path.stat().st_size == 0:
        return EnforcementV2DB(version="2.0", records=[])
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return EnforcementV2DB(**data)
    except json.JSONDecodeError as e:
        print(f"Warning: Corrupted enforcement_v2.json at {path}: {e}")
        return EnforcementV2DB(version="2.0", records=[])


def save_enforcement_v2(chat_id: str, db: EnforcementV2DB) -> None:
    path = _get_enforcement_v2_path(chat_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(db.model_dump(), f, indent=2)


def get_enforcement_v2_record(
    chat_id: str,
    node_id: str,
    target_id: str
) -> Optional[EnforcementRecordV2]:
    db = load_enforcement_v2(chat_id)
    
    for record in db.records:
        if record.node_id == node_id and record.target_id == target_id:
            return record
    
    return None


def generate_requirement_id(existing_requirements: List[Requirement]) -> str:
    if not existing_requirements:
        return "req-1"
    
    max_num = 0
    for req in existing_requirements:
        if req.id.startswith("req-"):
            try:
                num = int(req.id.split("-")[1])
                max_num = max(max_num, num)
            except (IndexError, ValueError):
                continue
    
    return f"req-{max_num + 1}"


def add_requirements(
    chat_id: str,
    node_id: str,
    target_id: str,
    requirements: List[dict]
) -> EnforcementRecordV2:
    db = load_enforcement_v2(chat_id)
    
    record = None
    for r in db.records:
        if r.node_id == node_id and r.target_id == target_id:
            record = r
            break
    
    if record is None:
        record = EnforcementRecordV2(
            chat_id=chat_id,
            node_id=node_id,
            target_kind="substep",
            target_id=target_id,
            requirements=[],
            verifications=[],
            tests=[],
            overall_verdict="not_done",
            timestamp=datetime.now().isoformat()
        )
        db.records.append(record)
    
    for req_data in requirements:
        req_id = generate_requirement_id(record.requirements)
        requirement = Requirement(
            id=req_id,
            description=req_data['description'],
            category=req_data['category'],
            source=req_data.get('source', 'auto')
        )
        record.requirements.append(requirement)
    
    record.timestamp = datetime.now().isoformat()
    save_enforcement_v2(chat_id, db)
    return record


def add_user_requirement(
    chat_id: str,
    node_id: str,
    target_id: str,
    description: str,
    category: str
) -> EnforcementRecordV2:
    return add_requirements(
        chat_id,
        node_id,
        target_id,
        [{'description': description, 'category': category, 'source': 'user'}]
    )


def update_verifications(
    chat_id: str,
    node_id: str,
    target_id: str,
    verifications: List[RequirementVerification]
) -> EnforcementRecordV2:
    db = load_enforcement_v2(chat_id)
    
    record = None
    for r in db.records:
        if r.node_id == node_id and r.target_id == target_id:
            record = r
            break
    
    if record is None:
        raise ValueError(f"No enforcement record found for {node_id}/{target_id}")
    
    # Merge: keep existing verifications for requirements NOT being updated
    incoming_ids = {v.requirement_id for v in verifications}
    kept = [v for v in record.verifications if v.requirement_id not in incoming_ids]
    record.verifications = kept + verifications
    
    record.overall_verdict = compute_overall_verdict(record)
    record.timestamp = datetime.now().isoformat()
    
    save_enforcement_v2(chat_id, db)
    return record


def update_tests(
    chat_id: str,
    node_id: str,
    target_id: str,
    tests: List[RequirementTest]
) -> EnforcementRecordV2:
    db = load_enforcement_v2(chat_id)
    
    record = None
    for r in db.records:
        if r.node_id == node_id and r.target_id == target_id:
            record = r
            break
    
    if record is None:
        raise ValueError(f"No enforcement record found for {node_id}/{target_id}")
    
    # Merge: keep existing tests for requirements NOT being updated
    incoming_ids = {t.requirement_id for t in tests}
    kept = [t for t in record.tests if t.requirement_id not in incoming_ids]
    record.tests = kept + tests
    
    record.timestamp = datetime.now().isoformat()
    
    save_enforcement_v2(chat_id, db)
    return record


def compute_overall_verdict(record: EnforcementRecordV2) -> str:
    if not record.verifications:
        return "not_done"
    
    requirement_ids = {req.id for req in record.requirements}
    verified_ids = {ver.requirement_id for ver in record.verifications}
    
    if requirement_ids != verified_ids:
        return "not_done"
    
    all_pass = all(ver.verdict == "pass" for ver in record.verifications)
    any_pass = any(ver.verdict == "pass" for ver in record.verifications)
    
    if all_pass:
        return "done"
    elif any_pass:
        return "partial"
    else:
        return "not_done"


def delete_requirement(
    chat_id: str,
    node_id: str,
    target_id: str,
    requirement_id: str
) -> bool:
    db = load_enforcement_v2(chat_id)
    
    for record in db.records:
        if record.node_id == node_id and record.target_id == target_id:
            original_len = len(record.requirements)
            record.requirements = [
                req for req in record.requirements
                if req.id != requirement_id
            ]
            
            if len(record.requirements) < original_len:
                record.verifications = [
                    ver for ver in record.verifications
                    if ver.requirement_id != requirement_id
                ]
                record.tests = [
                    test for test in record.tests
                    if test.requirement_id != requirement_id
                ]
                
                record.overall_verdict = compute_overall_verdict(record)
                record.timestamp = datetime.now().isoformat()
                
                save_enforcement_v2(chat_id, db)
                return True
    
    return False


def update_step_verification(
    chat_id: str,
    node_id: str,
    verification: 'StepVerification'
) -> EnforcementRecordV2:
    db = load_enforcement_v2(chat_id)
    
    record = None
    for r in db.records:
        if r.node_id == node_id and r.target_kind == "step":
            record = r
            break
    
    if record is None:
        record = EnforcementRecordV2(
            chat_id=chat_id,
            node_id=node_id,
            target_kind="step",
            target_id=node_id,
            requirements=[],
            verifications=[],
            tests=[],
            step_verification=verification,
            timestamp=datetime.now().isoformat()
        )
        db.records.append(record)
    else:
        record.step_verification = verification
        record.timestamp = datetime.now().isoformat()
    
    save_enforcement_v2(chat_id, db)
    return record


def delete_enforcement_v2_record(
    chat_id: str,
    node_id: str,
    target_id: str
) -> bool:
    db = load_enforcement_v2(chat_id)
    
    original_len = len(db.records)
    db.records = [
        r for r in db.records
        if not (r.node_id == node_id and r.target_id == target_id)
    ]
    
    if len(db.records) < original_len:
        save_enforcement_v2(chat_id, db)
        return True
    
    return False
