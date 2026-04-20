import sys
from pathlib import Path
from datetime import datetime
import json
import uuid

from backend.utils import get_project_root
from backend.globals.models import get_default_provider
from backend.globals.schemas import get_schema
from backend.knowledge.prompts.parse_unstructured import PARSE_UNSTRUCTURED_PROMPT
from backend.routes.knowledge_routes import (
    load_processing_log,
    save_processing_log,
    load_knowledge_base,
    save_knowledge_base,
    parse_markdown_sections,
    format_sections_for_llm,
)


def _collect_files(files: list[str]) -> list[Path]:
    root = get_project_root()
    unstructured_dir = root / ".zoro" / "rules" / "unstructured"
    unstructured_dir.mkdir(parents=True, exist_ok=True)

    if files:
        return [unstructured_dir / f for f in files]

    # Default: all markdown files in unstructured dir (exclude processed/)
    candidates = [
        p for p in unstructured_dir.glob("*.md")
        if p.is_file()
    ]
    return candidates


def cmd_kb_process(args) -> int:
    try:
        files = _collect_files(args.files or [])
        if not files:
            print("No unstructured KB files found.")
            return 0

        root = get_project_root()
        unstructured_dir = root / ".zoro" / "rules" / "unstructured"
        processed_dir = unstructured_dir / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)

        provider = get_default_provider()
        processing_log = load_processing_log()

        results = []

        for file_path in files:
            filename = file_path.name
            if not file_path.exists():
                results.append({"filename": filename, "success": False, "error": "File not found"})
                continue

            content = file_path.read_text(encoding="utf-8")
            sections = parse_markdown_sections(content)

            log_entry = processing_log["files"].get(filename, {})
            processed_count = log_entry.get("items_processed", 0)
            new_sections = sections[processed_count:]
            pre_count = len(new_sections)

            if pre_count == 0:
                results.append({
                    "filename": filename,
                    "success": True,
                    "items_added": 0,
                    "message": "No new items to process",
                })
                continue

            sections_text = format_sections_for_llm(new_sections)
            prompt = PARSE_UNSTRUCTURED_PROMPT.format(
                content=sections_text,
                expected_count=pre_count,
            )

            response = provider.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-5",
                response_format=get_schema({
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string", "enum": ["rule", "doc"]},
                                    "category": {"type": "string"},
                                    "title": {"type": "string"},
                                    "content": {"type": "string"},
                                    "context": {"type": ["string", "null"]},
                                    "evidence": {"type": ["string", "null"]},
                                    "confidence": {"type": ["number", "null"]},
                                    "decay": {"type": ["number", "null"]},
                                    "confidence_reasoning": {"type": ["string", "null"]},
                                    "decay_reasoning": {"type": ["string", "null"]},
                                },
                                "required": ["type", "category", "title", "content"],
                            },
                        }
                    },
                    "required": ["items"],
                }),
            )

            if not response:
                results.append({"filename": filename, "success": False, "error": "LLM returned empty response"})
                continue

            try:
                parsed = json.loads(response)
            except json.JSONDecodeError as e:
                results.append({"filename": filename, "success": False, "error": f"Invalid JSON from LLM: {e}"})
                continue

            items = parsed.get("items", [])
            post_count = len(items)
            if post_count != pre_count:
                results.append({
                    "filename": filename,
                    "success": False,
                    "error": f"Count mismatch: expected {pre_count}, got {post_count}",
                })
                continue

            timestamp = datetime.now().isoformat()
            newly_added_ids = []
            for item in items:
                item["item_id"] = str(uuid.uuid4())
                item["source_file"] = filename
                item["usage_count"] = 0
                item["is_favorite"] = False
                item["created_at"] = timestamp
                if item.get("confidence") is None:
                    item["confidence"] = 0.5
                if item.get("decay") is None:
                    item["decay"] = 0.5
                newly_added_ids.append(item["item_id"])

            kb = load_knowledge_base()
            kb["items"].extend(items)
            save_knowledge_base(kb)

            timestamp_str = datetime.now().strftime("%Y-%m-%d")
            processed_filename = f"{file_path.stem}_{timestamp_str}.md"
            processed_path = processed_dir / processed_filename
            processed_path.write_text(content, encoding="utf-8")

            processing_log["files"][filename] = {
                "last_processed": timestamp,
                "items_processed": len(sections),
                "runs": log_entry.get("runs", []) + [{
                    "timestamp": timestamp,
                    "items_added": post_count
                }]
            }
            save_processing_log(processing_log)

            results.append({
                "filename": filename,
                "success": True,
                "items_added": post_count,
                "newly_added_ids": newly_added_ids,
                "processed_path": str(processed_path.relative_to(root)),
            })

        total_added = sum(r.get("items_added", 0) for r in results)
        print(f"Processed {len(results)} file(s). Total items added: {total_added}")
        for r in results:
            status = "✓" if r.get("success") else "✗"
            msg = r.get("error") or r.get("message") or f"+{r.get('items_added', 0)}"
            print(f"{status} {r.get('filename')}: {msg}")

        return 0
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
