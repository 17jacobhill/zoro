import sys

from backend.cli.utils import (
    create_template_file,
    create_zoro_directories,
    ensure_agents_protocol_file,
    ensure_claude_protocol_file,
    print_section,
    setup_gitignore,
)
from backend.utils import DEFAULT_MODEL, DEFAULT_MODELS_BY_FEATURE


def cmd_init(args, save_config):
    print("Initializing Zoro in current project...")
    print(f"User: {args.user_name}\n")

    try:
        create_zoro_directories()

        print("\nCreating configuration files...")
        create_template_file("ZORO.md", "ZORO.md", overwrite=True)
        ensure_agents_protocol_file("AGENTS.md")
        ensure_claude_protocol_file("CLAUDE.md")
        create_template_file(".env.example", "env_example.txt")

        setup_gitignore()

        print("\nSaving configuration...")
        config = {
            "user_name": args.user_name,
            "enforcement_mode": "selective-verification",
            "rule_retrieval_source": "structured",
            "rule_test_evidence_enabled": True,
            "chat_history_source": "codex",
            "default_model": DEFAULT_MODEL,
            "llm_models": dict(DEFAULT_MODELS_BY_FEATURE),
            "processed_files": [],
        }
        save_config(config)
        print("  ✓ Created .zoro/config.json")

        print_section("SETUP COMPLETE!")
        print("\nNext steps:")
        print("1. Set up API key:")
        print("   - Copy .env.example to .env")
        print("   - Add your OPENAI_API_KEY to .env")
        print()
        print("2. Defaults applied:")
        print("   - enforcement_mode = selective-verification")
        print("   - chat_history_source = codex")
        print("   - rule_retrieval_source = structured")
        print()
        print("3. Agent protocol files:")
        print("   - Read ZORO.md for the canonical workflow protocol")
        print("   - Existing AGENTS.md content is preserved and prefixed with the Zoro shim")
        print("   - Existing CLAUDE.md content is preserved, with a short block added pointing to @ZORO.md")
        print()
        print("4. Start using the visualization workflow:")
        print("   - Extract a plan into .zoro/CURRENT_PLAN.md")
        print("   - Use `zoro update-step`, `zoro prove-rule`, and `zoro add-note` while coding")
        print()
    except Exception as e:
        print(f"\nError during initialization: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
