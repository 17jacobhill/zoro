from __future__ import annotations
from pathlib import Path
import json
from typing import Optional
from datetime import datetime

from backend.globals.schemas import (
    EnforcementDB,
    EnforcementRecord,
    VerifyResult,
    DoResult,
    TestResult,
)


def _get_enforcement_path(chat_id: str) -> Path:
    return Path.cwd() / ".zoro" / "generated" / "assistant" / chat_id / "enforcement.json"


def load_enforcement(chat_id: str) -> EnforcementDB:
    path = _get_enforcement_path(chat_id)
    if not path.exists():
        return EnforcementDB(records=[])
    
    if path.stat().st_size == 0:
        return EnforcementDB(records=[])
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return EnforcementDB(**data)
    except json.JSONDecodeError as e:
        print(f"Warning: Corrupted enforcement.json at {path}: {e}")
        return EnforcementDB(records=[])


def save_enforcement(chat_id: str, db: EnforcementDB) -> None:
    path = _get_enforcement_path(chat_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(db.model_dump(), f, indent=2)


def get_enforcement_record(
    chat_id: str,
    node_id: str,
    target_kind: str,
    target_id: str
) -> Optional[EnforcementRecord]:
    db = load_enforcement(chat_id)
    
    for record in db.records:
        if (record.node_id == node_id and 
            record.target_kind == target_kind and 
            record.target_id == target_id):
            return record
    
    return None


def upsert_enforcement_record(
    chat_id: str,
    node_id: str,
    target_kind: str,
    target_id: str,
    verify: Optional[VerifyResult] = None,
    do: Optional[DoResult] = None,
    test: Optional[TestResult] = None
) -> EnforcementRecord:
    db = load_enforcement(chat_id)
    
    existing = None
    for i, record in enumerate(db.records):
        if (record.node_id == node_id and 
            record.target_kind == target_kind and 
            record.target_id == target_id):
            existing = i
            break
    
    if existing is not None:
        record = db.records[existing]
        if verify is not None:
            record.verify = verify
        if do is not None:
            record.do = do
        if test is not None:
            record.test = test
    else:
        record = EnforcementRecord(
            node_id=node_id,
            target_kind=target_kind,
            target_id=target_id,
            verify=verify,
            do=do,
            test=test
        )
        db.records.append(record)
    
    save_enforcement(chat_id, db)
    return record


def delete_enforcement_record(
    chat_id: str,
    node_id: str,
    target_kind: str,
    target_id: str
) -> bool:
    db = load_enforcement(chat_id)
    
    original_len = len(db.records)
    db.records = [
        r for r in db.records
        if not (r.node_id == node_id and 
                r.target_kind == target_kind and 
                r.target_id == target_id)
    ]
    
    if len(db.records) < original_len:
        save_enforcement(chat_id, db)
        return True
    
    return False
