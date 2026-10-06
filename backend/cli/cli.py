#!/usr/bin/env python3

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True))

import sys
import argparse

from backend.cli.commands import cmd_init, update_step, add_note, prove_rule, verify_step, accept_risk
from backend.utils import get_project_root

# Config file path
CONFIG_PATH = get_project_root() / ".zoro/config.json"

def save_config(config):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    import json

    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Zoro CLI for the canonical visualization workflow'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
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

    # Update-step command
    update_step_parser = subparsers.add_parser(
        'update-step',
        help='Update visualization item status in the active plan'
    )
    update_step_parser.add_argument('step_id', help='Step ID to update')
    update_step_parser.add_argument('status', choices=['pending', 'in_progress', 'completed', 'blocked'], help='New status')
    update_step_parser.add_argument('--chat-id', help='Chat ID (auto-detect if not provided)')
    
    # Add-note command
    add_note_parser = subparsers.add_parser(
        'add-note',
        help='Add a note to a visualization plan item'
    )
    add_note_parser.add_argument('step_id', help='Step ID')
    add_note_parser.add_argument('note', help='Note text')
    add_note_parser.add_argument('--chat-id', help='Chat ID (auto-detect if not provided)')

    # Prove-rule command
    prove_rule_parser = subparsers.add_parser(
        'prove-rule',
        help='Prove a specific rule was followed with code evidence'
    )
    prove_rule_parser.add_argument('item_id', help='Item ID to update')
    prove_rule_parser.add_argument('--rule', required=True, help='Rule text to match')
    prove_rule_parser.add_argument('--explanation', dest='explanation', required=True, help='Detailed explanation')
    prove_rule_parser.add_argument('--file', action='append', help='File path (can be repeated)')
    prove_rule_parser.add_argument('--snippet', action='append', help='Code snippet (can be repeated; use escaped \\n for multiline evidence)')
    prove_rule_parser.add_argument('--line-range', action='append', help='Line range (can be repeated)')
    prove_rule_parser.add_argument('--verdict', choices=['pass', 'fail', 'unclear'], default='pass', help='Verdict')
    prove_rule_parser.add_argument('--test-name', help='Optional test name (when rule is testable)')
    prove_rule_parser.add_argument('--test-command', help='Optional test command that was run')
    prove_rule_parser.add_argument('--test-result', choices=['pass', 'fail', 'error'], help='Optional test result')
    prove_rule_parser.add_argument('--test-output', help='Optional test output (stdout/stderr summary)')
    prove_rule_parser.add_argument('--test-file', help='Optional test file path (temporary or permanent)')
    prove_rule_parser.add_argument('--chat-id', help='Chat ID (auto-detect if not provided)')
    prove_rule_parser.add_argument(
        '--snippet-max-lines',
        type=int,
        default=12,
        help='Maximum snippet lines to persist per --snippet block (default: 12)',
    )

    # Verify-step command — the only command that launches an external verifier.
    verify_step_parser = subparsers.add_parser(
        'verify-step',
        help='Run an external verifier for a step and import its result as evidence'
    )
    verify_step_parser.add_argument('step_id', help='Step ID to verify')
    verify_step_parser.add_argument('--verifier', required=True, help='Verifier id from .zoro/config.json\'s "verifiers" block')
    verify_step_parser.add_argument('--chat-id', help='Chat ID (auto-detect if not provided)')
    verify_step_parser.add_argument('--plan-id', help='Plan ID, if the active plan has a stable one')

    # Accept-risk command — separate human-authorized decision record.
    accept_risk_parser = subparsers.add_parser(
        'accept-risk',
        help='Record an authorized human acceptance of a PASS_WITH_RISK verifier result'
    )
    accept_risk_parser.add_argument('step_id', help='Step ID whose risk is being accepted')
    accept_risk_parser.add_argument('--invocation-id', required=True, help='The verify-step invocation id being accepted')
    accept_risk_parser.add_argument('--reason', required=True, help='Why this risk is being accepted')
    accept_risk_parser.add_argument('--expires-at', help='Optional ISO timestamp after which this acceptance no longer applies')
    accept_risk_parser.add_argument('--chat-id', help='Chat ID (auto-detect if not provided)')

    return parser.parse_args()

def main():
    args = parse_args()
    
    if args.command == 'init':
        cmd_init(args, save_config)
    elif args.command == 'update-step':
        update_step.callback(args.step_id, args.status, args.chat_id)
    elif args.command == 'add-note':
        add_note.callback(args.step_id, args.note, args.chat_id)
    elif args.command == 'prove-rule':
        if args.snippet_max_lines < 1:
            print("❌ --snippet-max-lines must be >= 1")
            sys.exit(1)
        files = tuple(args.file) if args.file else ()
        snippets = tuple(args.snippet) if args.snippet else ()
        line_ranges = tuple(args.line_range) if args.line_range else ()
        prove_rule.callback(
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
            args.chat_id,
            args.snippet_max_lines,
        )
    elif args.command == 'verify-step':
        verify_step.callback(args.step_id, args.verifier, args.chat_id, args.plan_id)
    elif args.command == 'accept-risk':
        accept_risk.callback(args.step_id, args.invocation_id, args.reason, args.expires_at, args.chat_id)
    else:
        print("Please specify a valid command. Use --help for more information")
        sys.exit(1)

def cli():
    main()

if __name__ == '__main__':
    cli()
