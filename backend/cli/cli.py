#!/usr/bin/env python3

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))

import sys
import argparse
from pathlib import Path
import json

from backend.cli.commands.learning import cmd_init, cmd_process, cmd_list_tags, cmd_tag_chat, cmd_observation_eval
from backend.cli.commands.knowledge import cmd_kb_process
from backend.cli.commands.assistant import cmd_search, cmd_plan, cmd_plan_iter, cmd_plan_edit, cmd_plan_extend, cmd_chat_recs
from backend.cli.commands.tracking import update_step, add_note, complete_step, update_substep, add_manual_rule, set_output
from backend.cli.commands.visualization import viz_update, viz_verify_rule, viz_verify_step
from backend.cli.commands.messages import cmd_messages
from backend.utils import get_project_root

# Config file path
CONFIG_PATH = get_project_root() / ".zoro/config.json"

def load_config():
    if not CONFIG_PATH.exists():
        return None
    
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def save_config(config):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)

def mark_file_processed(filename):
    config = load_config()
    if not config:
        config = {"user_name": "", "processed_files": []}
    
    if "processed_files" not in config:
        config["processed_files"] = []
    
    if filename not in config["processed_files"]:
        config["processed_files"].append(filename)
        save_config(config)

def parse_args():
    parser = argparse.ArgumentParser(
        description='Learning system CLI - process chat logs and search rules'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Process command
    process_parser = subparsers.add_parser(
        'process',
        help='Process markdown chat logs into tasks and learn rules with trajectory analysis'
    )
    process_parser.add_argument(
        'file_path',
        nargs='?',
        help='Path to markdown chat file (optional - processes all unprocessed files if not provided)'
    )
    process_parser.add_argument(
        '--user-name',
        type=str,
        help='Name of the user for personalized learning (optional - uses config if not provided)'
    )
    
    # Init command
    init_parser = subparsers.add_parser(
        'init',
        help='Initialize zoro in the current project'
    )
    init_parser.add_argument(
        '--user-name',
        type=str,
        required=True,
        help='Your name for personalized learning'
    )
    
    # Search command
    search_parser = subparsers.add_parser(
        'search',
        help='Search for relevant rules'
    )
    search_parser.add_argument(
        'query',
        help='Search query string'
    )
    search_parser.add_argument(
        '--limit',
        type=int,
        default=5,
        help='Number of results to return (default: 5)'
    )
    search_parser.add_argument(
        '--output',
        type=str,
        help='Output markdown file path (e.g., .clinerules/context.md)'
    )
    search_parser.add_argument(
        '--tags',
        type=str,
        help='Filter by tags (comma-separated, e.g., "frontend,planning")'
    )

    # KB process command
    kb_process_parser = subparsers.add_parser(
        'kb-process',
        help='Process unstructured knowledge base files into structured rules'
    )
    kb_process_parser.add_argument(
        'files',
        nargs='*',
        help='Unstructured KB markdown filenames (from .zoro/rules/unstructured). If omitted, processes all.'
    )
    
    # Messages command
    messages_parser = subparsers.add_parser(
        'messages',
        help='Extract and display user messages from a chat file'
    )
    messages_parser.add_argument(
        'file_path',
        help='Path to markdown chat file'
    )
    
    # Plan command
    plan_parser = subparsers.add_parser(
        'plan',
        help='Generate execution plan with rules and failure detection'
    )
    plan_parser.add_argument(
        'query',
        help='Task description to plan for'
    )
    plan_parser.add_argument(
        '--chat-id',
        type=str,
        help='Chat ID to associate this plan with (for persistence)'
    )
    plan_parser.add_argument(
        '--output',
        type=str,
        help='Output markdown file path (e.g., .rules/zoro_plan.md)'
    )
    plan_parser.add_argument(
        '--tags',
        type=str,
        help='Filter by tags (comma-separated, e.g., "pals,ui")'
    )
    
    # Plan-iter command (generates new code-style steps)
    plan_iter_parser = subparsers.add_parser(
        'plan-iter',
        help='Generate new code-style steps after planning phase'
    )
    plan_iter_parser.add_argument(
        'query',
        help='Implementation strategy description'
    )
    plan_iter_parser.add_argument(
        '--chat-id',
        type=str,
        required=True,
        help='Chat ID to add steps to'
    )
    plan_iter_parser.add_argument(
        '--from-step',
        type=int,
        required=True,
        help='Starting step number for new code-style steps (e.g., --from-step 3)'
    )

    # Plan-edit command (edits existing steps)
    plan_edit_parser = subparsers.add_parser(
        'plan-edit',
        help='Edit existing steps in plan'
    )
    plan_edit_parser.add_argument(
        'query',
        help='Edit description (what to change)'
    )
    plan_edit_parser.add_argument(
        '--chat-id',
        type=str,
        required=True,
        help='Chat ID to edit'
    )
    plan_edit_parser.add_argument(
        '--from-step',
        type=int,
        required=True,
        help='Edit step-N and all subsequent steps (e.g., --from-step 4)'
    )
    plan_edit_parser.add_argument(
        '--output',
        type=str,
        help='Output markdown file path (e.g., .rules/zoro_plan.md)'
    )


    # Update-step command
    update_step_parser = subparsers.add_parser(
        'update-step',
        help='Update step status in plan'
    )
    update_step_parser.add_argument('step_id', help='Step ID to update')
    update_step_parser.add_argument('status', choices=['pending', 'in_progress', 'completed', 'blocked'], help='New status')
    update_step_parser.add_argument('--chat-id', help='Chat ID (auto-detect if not provided)')
    
    # Add-note command
    add_note_parser = subparsers.add_parser(
        'add-note',
        help='Add note to step audit trail'
    )
    add_note_parser.add_argument('step_id', help='Step ID')
    add_note_parser.add_argument('note', help='Note text')
    add_note_parser.add_argument('--chat-id', help='Chat ID (auto-detect if not provided)')
    
    # Complete-step command
    complete_step_parser = subparsers.add_parser(
        'complete-step',
        help='Mark step as completed with optional rule tracking'
    )
    complete_step_parser.add_argument('step_id', help='Step ID to complete')
    complete_step_parser.add_argument('--rules-used', default='', help='Comma-separated rule IDs')
    complete_step_parser.add_argument('--note', default='', help='Optional note')
    complete_step_parser.add_argument('--chat-id', help='Chat ID (auto-detect if not provided)')
    
    # Update-substep command
    update_substep_parser = subparsers.add_parser(
        'update-substep',
        help='Update substep status'
    )
    update_substep_parser.add_argument('step_id', help='Parent step ID')
    update_substep_parser.add_argument('substep_id', help='Substep ID')
    update_substep_parser.add_argument('status', choices=['pending', 'completed'], help='New status')
    update_substep_parser.add_argument('--chat-id', help='Chat ID (auto-detect if not provided)')

    # Add-manual-rule command
    add_manual_rule_parser = subparsers.add_parser(
        'add-manual-rule',
        help='Add a manual RuleRef to a plan node (Assistant)'
    )
    add_manual_rule_parser.add_argument('step_id', help='Step/node ID (e.g., step-2)')
    add_manual_rule_parser.add_argument('description', help='Rule text to add')
    add_manual_rule_parser.add_argument('--name', default=None, help='Short rule name/label (default: manual)')
    add_manual_rule_parser.add_argument('--source', default=None, help='Rule source (default: manual)')
    add_manual_rule_parser.add_argument('--rule-id', default=None, help='Optional explicit rule_id (default: auto-generated)')
    add_manual_rule_parser.add_argument('--chat-id', help='Chat ID (auto-detect if not provided)')
    
    # Set-output command
    set_output_parser = subparsers.add_parser(
        'set-output',
        help='Set output field for a step (e.g., save planning strategy)'
    )
    set_output_parser.add_argument('step_id', help='Step/node ID (e.g., step-2)')
    set_output_parser.add_argument('output', help='Output text to save')
    set_output_parser.add_argument('--chat-id', help='Chat ID (auto-detect if not provided)')
    
    # Plan-extend command
    plan_extend_parser = subparsers.add_parser(
        'plan-extend',
        help='Extend plan by generating multiple new steps using LLM'
    )
    plan_extend_parser.add_argument('feature_request', help='Feature request to build upon the existing plan')
    plan_extend_parser.add_argument('--chat-id', required=True, help='Chat ID')
    
    chat_recs_parser = subparsers.add_parser(
        'chat-recs',
        help='Generate lightweight recommendations from your most recent VS Code Claude-Dev chat'
    )
    chat_recs_parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='Max number of most recent messages to consider (default: 100)'
    )
    chat_recs_parser.add_argument(
        '--path',
        type=str,
        help='Optional override path to api_conversation_history.json'
    )
    chat_recs_parser.add_argument(
        '--format',
        choices=['json', 'text'],
        default='json',
        help='Output format (default: json)'
    )
    chat_recs_parser.add_argument(
        '--chat-id',
        type=str,
        help='Optional assistant chat_id to load plan context for GPT recommendations'
    )
    chat_recs_parser.add_argument(
        '--debug-prompt',
        action='store_true',
        help='Print the raw LLM prompt (system + user) to stdout (danger: may include secrets)'
    )
    
    # List-tags command
    list_tags_parser = subparsers.add_parser(
        'list-tags',
        help='List all tags with usage counts'
    )
    
    # Tag-chat command
    tag_chat_parser = subparsers.add_parser(
        'tag-chat',
        help='Add or remove tags from a chat'
    )
    tag_chat_parser.add_argument('chat', help='Chat name (without .json extension)')
    tag_chat_parser.add_argument('--add', default='', help='Comma-separated tags to add')
    tag_chat_parser.add_argument('--remove', default='', help='Comma-separated tags to remove')

    # Viz-update command
    viz_update_parser = subparsers.add_parser(
        'viz-update',
        help='Update visualization plan item status'
    )
    viz_update_parser.add_argument('item_id', help='Item ID to update')
    viz_update_parser.add_argument('status', choices=['in_progress', 'completed', 'pending'], help='New status')
    viz_update_parser.add_argument('--chat-id', help='Chat ID (auto-detect if not provided)')
    
    # Prove-rule command
    prove_rule_parser = subparsers.add_parser(
        'prove-rule',
        help='Prove a specific rule was followed with code evidence'
    )
    prove_rule_parser.add_argument('item_id', help='Item ID to update')
    prove_rule_parser.add_argument('--rule', required=True, help='Rule text to match')
    prove_rule_parser.add_argument('--explanation', required=True, help='Detailed explanation')
    prove_rule_parser.add_argument('--file', action='append', required=True, help='File path (can be repeated)')
    prove_rule_parser.add_argument('--snippet', action='append', required=True, help='Code snippet (can be repeated; use escaped \\n for multiline evidence)')
    prove_rule_parser.add_argument('--line-range', action='append', help='Line range (can be repeated)')
    prove_rule_parser.add_argument('--verdict', choices=['pass', 'fail', 'unclear'], default='pass', help='Verdict')
    prove_rule_parser.add_argument('--test-name', help='Optional test name (when rule is testable)')
    prove_rule_parser.add_argument('--test-command', help='Optional test command that was run')
    prove_rule_parser.add_argument('--test-result', choices=['pass', 'fail', 'error'], help='Optional test result')
    prove_rule_parser.add_argument('--test-output', help='Optional test output (stdout/stderr summary)')
    prove_rule_parser.add_argument('--test-file', help='Optional test file path (temporary or permanent)')
    prove_rule_parser.add_argument('--chat-id', help='Chat ID (auto-detect if not provided)')

    # Viz-verify-rule command (backwards-compatible alias)
    viz_verify_rule_parser = subparsers.add_parser(
        'viz-verify-rule',
        help='Deprecated alias for prove-rule'
    )
    viz_verify_rule_parser.add_argument('item_id', help='Item ID to update')
    viz_verify_rule_parser.add_argument('--rule', required=True, help='Rule text to match')
    viz_verify_rule_parser.add_argument('--explanation', required=True, help='Detailed explanation')
    viz_verify_rule_parser.add_argument('--file', action='append', required=True, help='File path (can be repeated)')
    viz_verify_rule_parser.add_argument('--snippet', action='append', required=True, help='Code snippet (can be repeated; use escaped \\n for multiline evidence)')
    viz_verify_rule_parser.add_argument('--line-range', action='append', help='Line range (can be repeated)')
    viz_verify_rule_parser.add_argument('--verdict', choices=['pass', 'fail', 'unclear'], default='pass', help='Verdict')
    viz_verify_rule_parser.add_argument('--test-name', help='Optional test name (when rule is testable)')
    viz_verify_rule_parser.add_argument('--test-command', help='Optional test command that was run')
    viz_verify_rule_parser.add_argument('--test-result', choices=['pass', 'fail', 'error'], help='Optional test result')
    viz_verify_rule_parser.add_argument('--test-output', help='Optional test output (stdout/stderr summary)')
    viz_verify_rule_parser.add_argument('--test-file', help='Optional test file path (temporary or permanent)')
    viz_verify_rule_parser.add_argument('--chat-id', help='Chat ID (auto-detect if not provided)')
    
    # Viz-verify-step command
    viz_verify_step_parser = subparsers.add_parser(
        'viz-verify-step',
        help='Verify entire step is complete with evidence'
    )
    viz_verify_step_parser.add_argument('item_id', help='Item ID to update')
    viz_verify_step_parser.add_argument('--explanation', required=True, help='What was accomplished')
    viz_verify_step_parser.add_argument('--file', action='append', help='File path (can be repeated)')
    viz_verify_step_parser.add_argument('--snippet', action='append', help='Code snippet (can be repeated; use escaped \\n for multiline evidence)')
    viz_verify_step_parser.add_argument('--line-range', action='append', help='Line range (can be repeated)')
    viz_verify_step_parser.add_argument('--output', default=None, help='Output file/URL (optional)')
    viz_verify_step_parser.add_argument('--verdict', choices=['pass', 'fail', 'unclear'], default='pass', help='Verdict')
    viz_verify_step_parser.add_argument('--chat-id', help='Chat ID (auto-detect if not provided)')

    # Observation-eval command
    obs_eval_parser = subparsers.add_parser(
        'observation-eval',
        help='Run observation evaluation with different ablation settings'
    )
    obs_eval_parser.add_argument(
        'file_path',
        help='Path to markdown chat file'
    )
    obs_eval_parser.add_argument(
        '--user-name',
        type=str,
        help='Name of the user for personalized learning (optional - uses config if not provided)'
    )
    obs_eval_parser.add_argument(
        '--no-task-chunking',
        action='store_true',
        help='Process the entire file as a single task'
    )
    obs_eval_parser.add_argument(
        '--no-evidence',
        action='store_true',
        help='Use a prompt that does not ask for evidence, confidence, or decay'
    )
    obs_eval_parser.add_argument(
        '--rules-only',
        action='store_true',
        help='Use a prompt that only asks for rules, with no trajectory analysis'
    )

    return parser.parse_args()

def main():
    args = parse_args()
    
    if args.command == 'init':
        cmd_init(args, save_config)
    elif args.command == 'process':
        cmd_process(args, load_config, mark_file_processed)
    elif args.command == 'observation-eval':
        cmd_observation_eval(args, load_config)
    elif args.command == 'search':
        cmd_search(args)
    elif args.command == 'messages':
        cmd_messages(args)
    elif args.command == 'plan':
        cmd_plan(args)
    elif args.command == 'plan-iter':
        cmd_plan_iter(args)
    elif args.command == 'plan-edit':
        cmd_plan_edit(args)
    elif args.command == 'update-step':
        update_step.callback(args.step_id, args.status, args.chat_id)
    elif args.command == 'add-note':
        add_note.callback(args.step_id, args.note, args.chat_id)
    elif args.command == 'complete-step':
        complete_step.callback(args.step_id, args.rules_used, args.note, args.chat_id)
    elif args.command == 'update-substep':
        update_substep.callback(args.step_id, args.substep_id, args.status, args.chat_id)
    elif args.command == 'add-manual-rule':
        add_manual_rule.callback(args.step_id, args.description, args.name, args.source, args.rule_id, args.chat_id)
    elif args.command == 'set-output':
        set_output(args.step_id, args.output, args.chat_id)
    elif args.command == 'plan-extend':
        cmd_plan_extend(args)
    elif args.command == 'kb-process':
        cmd_kb_process(args)
    elif args.command == 'chat-recs':
        cmd_chat_recs(args)
    elif args.command == 'list-tags':
        cmd_list_tags(args)
    elif args.command == 'tag-chat':
        cmd_tag_chat(args)
    elif args.command == 'viz-update':
        viz_update.callback(args.item_id, args.status, args.chat_id)
    elif args.command in ('prove-rule', 'viz-verify-rule'):
        files = tuple(args.file) if args.file else ()
        snippets = tuple(args.snippet) if args.snippet else ()
        line_ranges = tuple(args.line_range) if args.line_range else ()
        viz_verify_rule.callback(
            args.item_id,
            args.rule,
            args.explanation,
            files,
            snippets,
            line_ranges,
            args.verdict,
            args.test_name,
            args.test_command,
            args.test_result,
            args.test_output,
            args.test_file,
            args.chat_id
        )
    elif args.command == 'viz-verify-step':
        files = tuple(args.file) if args.file else ()
        snippets = tuple(args.snippet) if args.snippet else ()
        line_ranges = tuple(args.line_range) if args.line_range else ()
        viz_verify_step.callback(args.item_id, args.explanation, files, snippets, line_ranges, args.output, args.verdict, args.chat_id)
    else:
        print("Please specify a valid command. Use --help for more information")
        sys.exit(1)

def cli():
    main()

if __name__ == '__main__':
    cli()
