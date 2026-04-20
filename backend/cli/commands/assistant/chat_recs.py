import json
from typing import Optional

from backend.assistant.chat_recommendations import get_chat_recommendations


def cmd_chat_recs(args) -> int:
    path: Optional[str] = getattr(args, "path", None)
    limit: int = getattr(args, "limit", 100)
    fmt: str = getattr(args, "format", "json")
    chat_id: Optional[str] = getattr(args, "chat_id", None)
    debug_prompt: bool = bool(getattr(args, "debug_prompt", False))

    result = get_chat_recommendations(
        chat_id=chat_id,
        path=path,
        limit_messages=limit,
        debug_prompt=debug_prompt,
    )

    if fmt == "text":
        recs = result.get("recommendations") or []
        source = result.get("source")
        if source:
            print(f"Source: {source.get('path')}")
            print(f"Updated: {source.get('mtime')}")
            print(f"Messages used: {source.get('message_count')} (truncated={source.get('truncated')})")
            print("-")
        for i, rec in enumerate(recs[:2], start=1):
            print(f"{i}. {rec.get('text')}")
            reason = rec.get("reason")
            if reason:
                print(f"   Reason: {reason}")
        return 0

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0
