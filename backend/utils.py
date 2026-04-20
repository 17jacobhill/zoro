import re
import json
from pathlib import Path

def get_project_root() -> Path:
    return Path.cwd()

def get_enforcement_mode() -> str:
    config_path = get_project_root() / ".zoro" / "config.json"
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                mode = config.get("enforcement_mode", "verification")
                
                # Validate enforcement_mode
                valid_modes = ["verification", "no-verification", "selective-verification"]
                if mode not in valid_modes:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Invalid enforcement_mode '{mode}' in config, defaulting to 'verification'. Valid options: {valid_modes}")
                    return "verification"
                
                return mode
        except Exception:
            return "verification"
    return "verification"

def strip_markdown_json(text: str) -> str:
    text = re.sub(r'^```json\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^```\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'```$', '', text)
    return text.strip()


def get_rule_retrieval_source_from_config() -> str:
    config_path = get_project_root() / ".zoro" / "config.json"
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                source = config.get("rule_retrieval_source", "structured")
                
                if source not in ["structured", "unstructured"]:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Invalid rule_retrieval_source '{source}' in config, defaulting to 'structured'")
                    return "structured"
                
                return source
        except Exception:
            return "structured"
    return "structured"


def get_rule_test_evidence_enabled() -> bool:
    config_path = get_project_root() / ".zoro" / "config.json"
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                enabled = config.get("rule_test_evidence_enabled", False)
                return bool(enabled)
        except Exception:
            return False
    return False


def get_chat_history_source_from_config() -> str:
    config_path = get_project_root() / ".zoro" / "config.json"
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                source = config.get("chat_history_source", "cline")
                if source not in ["cline", "codex"]:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Invalid chat_history_source '{source}' in config, defaulting to 'cline'")
                    return "cline"
                return source
        except Exception:
            return "cline"
    return "cline"
