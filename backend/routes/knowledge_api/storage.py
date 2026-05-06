"""Compatibility shim.

Knowledge storage utilities moved to `backend.knowledge.services.storage`.
This module remains as a re-export layer to avoid breaking existing imports.
"""

from backend.knowledge.services.storage import (
    extract_unique_categories,
    format_sections_for_llm,
    increment_rule_usage_count,
    load_knowledge_base,
    load_manual_favorites,
    load_processing_log,
    manual_favorites_path,
    parse_markdown_sections,
    save_knowledge_base,
    save_manual_favorites,
    save_processing_log,
)
