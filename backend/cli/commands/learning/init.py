import sys
from pathlib import Path
from backend.cli.utils import (
    create_zoro_directories,
    setup_gitignore,
    create_template_file,
    print_section
)


def cmd_init(args, save_config):
    print("Initializing Zoro in current project...")
    print(f"User: {args.user_name}\n")
    
    try:
        # Create directories
        create_zoro_directories()
        
        # Create template files
        print("\nCreating configuration files...")
        create_template_file(".clinerules/zoro_integration.md", "selective_verification.md", overwrite=True)
        create_template_file("AGENTS.md", "agents_codex.md")
        create_template_file(".env.example", "env_example.txt")
        
        # Update .gitignore
        setup_gitignore()
        
        # Save config with user name
        print("\nSaving configuration...")
        config = {
            "user_name": args.user_name,
            "enforcement_mode": "selective-verification",
            "rule_retrieval_source": "structured",
            "rule_test_evidence_enabled": False,
            "chat_history_source": "codex",
            "show_learner_tab": False,
            "show_assistant_tab": False,
            "show_knowledge_base_tab": True,
            "processed_files": []
        }
        save_config(config)
        print("  ✓ Created .zoro/config.json")
        
        # Success message
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
        print("3. Export Cline chat (optional, only if using Cline):")
        print("   - Click menu in Cline")
        print("   - Export Chat → Save to .zoro/chat_history/")
        print()
        print("4. Process chat to learn rules:")
        print(f"   zoro process .zoro/chat_history/<file>.md --user-name {args.user_name}")
        print()
        print("5. Search rules:")
        print("   zoro search \"your query\"")
        print()
        
    except Exception as e:
        print(f"\nError during initialization: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
