import json
import logging
import re
from pathlib import Path


DEFAULT_MODEL = "gpt-5"
DEFAULT_MODELS_BY_FEATURE = {
    "plan_extraction": DEFAULT_MODEL,
    "plan_enrichment": DEFAULT_MODEL,
    "plan_refine_substeps": DEFAULT_MODEL,
    "rule_learning": DEFAULT_MODEL,
    "supervisor": DEFAULT_MODEL,
    "enforcement": DEFAULT_MODEL,
    "knowledge_category_merge": DEFAULT_MODEL,
    "knowledge_rule_refinement": DEFAULT_MODEL,
    "knowledge_parse_unstructured": DEFAULT_MODEL,
    "knowledge_parse_repo_instructions": DEFAULT_MODEL,
    "knowledge_duplicate_detection": DEFAULT_MODEL,
    "chat_parser_task_labeling": DEFAULT_MODEL,
}


def get_project_root() -> Path:
    return Path.cwd()


def _load_config() -> dict:
    config_path = get_project_root() / ".zoro" / "config.json"
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_enforcement_mode() -> str:
    config = _load_config()
    mode = config.get("enforcement_mode", "verification")

    valid_modes = ["verification", "no-verification", "selective-verification"]
    if mode not in valid_modes:
        logger = logging.getLogger(__name__)
        logger.warning(
            "Invalid enforcement_mode '%s' in config, defaulting to 'verification'. Valid options: %s",
            mode,
            valid_modes,
        )
        return "verification"

    return mode


def strip_markdown_json(text: str) -> str:
    text = re.sub(r"^```json\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^```\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"```$", "", text)
    return text.strip()


def get_rule_retrieval_source_from_config() -> str:
    config = _load_config()
    source = config.get("rule_retrieval_source", "structured")

    if source not in ["structured", "unstructured"]:
        logger = logging.getLogger(__name__)
        logger.warning(
            "Invalid rule_retrieval_source '%s' in config, defaulting to 'structured'",
            source,
        )
        return "structured"

    return source


def get_rule_test_evidence_enabled() -> bool:
    config = _load_config()
    enabled = config.get("rule_test_evidence_enabled", True)
    return bool(enabled)


def get_chat_history_source_from_config() -> str:
    config = _load_config()
    source = config.get("chat_history_source", "cline")
    if source not in ["cline", "codex", "claude"]:
        logger = logging.getLogger(__name__)
        logger.warning(
            "Invalid chat_history_source '%s' in config, defaulting to 'cline'",
            source,
        )
        return "cline"
    return source


def get_verifiers_config():
    """Strictly-validated `.zoro/config.json["verifiers"]` accessor.

    Deliberately does NOT call `_load_config()` (which swallows every
    read/parse error into `{}`) or otherwise degrade silently — this
    config drives literal subprocess argv for a security gate
    (backend/verifiers/security_audit.py's build_argv()), so a malformed
    file, a non-object `verifiers` value, or an invalid verifier entry
    must raise `VerifierConfigError` and block `verify-step` from running
    at all, rather than silently behaving as "no verifiers configured".
    A config.json that simply doesn't exist yet is a legitimate empty
    state (not every project uses this feature), not an error.
    """
    import json as _json

    from pydantic import ValidationError

    from backend.verifiers.schemas import VerifierConfigError, VerifiersConfig

    config_path = get_project_root() / ".zoro" / "config.json"
    if not config_path.exists():
        return VerifiersConfig()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw = _json.load(f)
    except (OSError, ValueError) as exc:
        raise VerifierConfigError(f"Could not read .zoro/config.json: {exc}") from exc

    if not isinstance(raw, dict):
        raise VerifierConfigError(".zoro/config.json must be a JSON object")

    raw_verifiers = raw.get("verifiers", {})
    if not isinstance(raw_verifiers, dict):
        raise VerifierConfigError(
            f"'verifiers' in .zoro/config.json must be an object, got {type(raw_verifiers).__name__}"
        )

    try:
        return VerifiersConfig(verifiers=raw_verifiers)
    except ValidationError as exc:
        raise VerifierConfigError(f"Invalid 'verifiers' config in .zoro/config.json: {exc}") from exc


def get_default_model_from_config() -> str:
    config = _load_config()
    model = config.get("default_model", DEFAULT_MODEL)
    return str(model).strip() or DEFAULT_MODEL


def get_llm_model_for_feature(feature: str, fallback: str | None = None) -> str:
    config = _load_config()
    configured_default = get_default_model_from_config()
    configured_map = config.get("llm_models", {})
    if not isinstance(configured_map, dict):
        configured_map = {}

    value = configured_map.get(feature)
    if isinstance(value, str) and value.strip():
        return value.strip()

    if fallback and str(fallback).strip():
        return str(fallback).strip()

    if feature in DEFAULT_MODELS_BY_FEATURE:
        return DEFAULT_MODELS_BY_FEATURE[feature]

    return configured_default


def get_llm_models_snapshot() -> dict:
    config = _load_config()
    configured_default = get_default_model_from_config()
    configured_map = config.get("llm_models", {})
    if not isinstance(configured_map, dict):
        configured_map = {}

    merged = dict(DEFAULT_MODELS_BY_FEATURE)
    for key, value in configured_map.items():
        if isinstance(value, str) and value.strip():
            merged[str(key)] = value.strip()

    return {
        "default_model": configured_default,
        "llm_models": merged,
    }
