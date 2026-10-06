import json

from backend.visualization.services.chat_source_registry import get_adapter, parse_chat_messages

CODEX_LINES = [
    {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "hello"}],
        },
    },
    {
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "hi there"}],
        },
    },
]
CODEX_RAW = "\n".join(json.dumps(line) for line in CODEX_LINES)

CLINE_RAW = json.dumps(
    {
        "messages": [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
    }
)

CLAUDE_LINES = [
    {"type": "user", "isSidechain": False, "message": {"role": "user", "content": "hello"}},
    {
        "type": "assistant",
        "isSidechain": False,
        "message": {"role": "assistant", "content": [{"type": "text", "text": "hi there"}]},
    },
    # Non-conversational record types must be skipped, not crash the parser.
    {"type": "file-history-snapshot", "data": {}},
    # A sidechain (sub-agent) turn must be excluded from the transcript.
    {"type": "assistant", "isSidechain": True, "message": {"role": "assistant", "content": "side task output"}},
]
CLAUDE_RAW = "\n".join(json.dumps(line) for line in CLAUDE_LINES)


def test_explicit_codex_source_parses_codex_shaped_content():
    messages = parse_chat_messages(CODEX_RAW, "codex")
    assert [m["role"] for m in messages] == ["user", "assistant"]


def test_explicit_cline_source_parses_the_generic_messages_shape():
    messages = parse_chat_messages(CLINE_RAW, "cline")
    assert [m["role"] for m in messages] == ["user", "assistant"]


def test_explicit_claude_source_parses_claude_shaped_content_and_excludes_sidechains():
    messages = parse_chat_messages(CLAUDE_RAW, "claude")
    assert len(messages) == 2
    assert [m["role"] for m in messages] == ["user", "assistant"]


def test_no_recorded_source_falls_back_to_codex_for_a_jsonl_path_not_live_config(monkeypatch):
    # Regression guard: a session created before chat_history_source was
    # recorded (or a hand-built fixture) must still parse as Codex when
    # its file is .jsonl, even if live config now defaults to cline.
    import backend.visualization.services.chat_source_registry as registry

    monkeypatch.setattr(registry, "get_chat_history_source_from_config", lambda: "cline")
    messages = parse_chat_messages(CODEX_RAW, None, file_path="/some/path/demo.jsonl")
    assert [m["role"] for m in messages] == ["user", "assistant"]


def test_no_recorded_source_and_no_jsonl_path_falls_back_to_live_config(monkeypatch):
    import backend.visualization.services.chat_source_registry as registry

    monkeypatch.setattr(registry, "get_chat_history_source_from_config", lambda: "cline")
    messages = parse_chat_messages(CLINE_RAW, None, file_path="/some/path/history.json")
    assert [m["role"] for m in messages] == ["user", "assistant"]


def test_get_adapter_prefers_an_explicit_source_over_the_jsonl_fallback():
    adapter = get_adapter("claude", file_path="/some/path/demo.jsonl")
    assert adapter["parse_messages"].__name__ == "parse_claude_jsonl_messages"


def test_unknown_source_string_does_not_crash_and_falls_back_safely(monkeypatch):
    import backend.visualization.services.chat_source_registry as registry

    monkeypatch.setattr(registry, "get_chat_history_source_from_config", lambda: "cline")
    messages = parse_chat_messages(CLINE_RAW, "some-made-up-source")
    assert [m["role"] for m in messages] == ["user", "assistant"]
