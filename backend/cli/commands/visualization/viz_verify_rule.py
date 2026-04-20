import click
from datetime import datetime
import unicodedata
from backend.visualization.services.plan_tracker import (
    load_plan_data,
    save_plan_data,
    get_chat_id_from_plan_md,
    find_item_by_id,
    collect_rules_for_item
)
from backend.visualization.services.visualization_manager import _recalculate_inherited_rules
from backend.utils import get_rule_test_evidence_enabled


def normalize_text(text):
    text = text.lower()
    text = text.replace('—', '-').replace('–', '-')
    text = text.replace('"', '"').replace('"', '"').replace(''', "'").replace(''', "'")
    text = unicodedata.normalize('NFKD', text)
    text = ' '.join(text.split())
    return text


def decode_cli_snippet(snippet: str) -> str:
    return (
        snippet
        .replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\r", "\r")
    )


@click.command()
@click.argument('item_id')
@click.option('--rule', required=True, help='Rule text to match')
@click.option('--explanation', required=True, help='Detailed explanation of how the rule was followed')
@click.option('--file', 'files', multiple=True, required=True, help='File path (can be repeated)')
@click.option('--snippet', 'snippets', multiple=True, required=True, help='Code snippet (can be repeated). Use escaped \\n for multiline evidence.')
@click.option('--line-range', 'line_ranges', multiple=True, help='Line range (optional, can be repeated)')
@click.option('--verdict', type=click.Choice(['pass', 'fail', 'unclear']), default='pass')
@click.option('--test-name', default=None, help='Optional test name (when rule is testable)')
@click.option('--test-command', default=None, help='Optional test command that was run')
@click.option('--test-result', type=click.Choice(['pass', 'fail', 'error']), default=None, help='Optional test result')
@click.option('--test-output', default=None, help='Optional test output (stdout/stderr summary)')
@click.option('--test-file', default=None, help='Optional test file path (temporary or permanent)')
@click.option('--chat-id', default=None, help='Chat ID (auto-detect if not provided)')
def viz_verify_rule(item_id, rule, explanation, files, snippets, line_ranges, verdict, test_name, test_command, test_result, test_output, test_file, chat_id):
    if not chat_id:
        chat_id = get_chat_id_from_plan_md()
        if not chat_id:
            click.echo("❌ No active visualization plan found")
            return
    
    if len(files) != len(snippets):
        click.echo(f"❌ Number of --file ({len(files)}) and --snippet ({len(snippets)}) must match")
        return
    
    if line_ranges and len(line_ranges) != len(files):
        click.echo(f"❌ If using --line-range, must provide same number as --file")
        return

    for idx, snippet in enumerate(snippets):
        if "\n" in snippet or "\r" in snippet:
            file_ref = files[idx] if idx < len(files) else "unknown file"
            click.echo("❌ --snippet cannot contain literal newline characters")
            click.echo(f"   Offending file: {file_ref}")
            click.echo("   Keep the command on one line and use escaped \\n inside --snippet for multiline evidence.")
            return
    
    plan_data = load_plan_data(chat_id)
    if not plan_data:
        click.echo(f"❌ No plan found for chat ID: {chat_id}")
        return
    
    item = find_item_by_id(plan_data['plan']['items'], item_id)
    if not item:
        click.echo(f"❌ Item {item_id} not found")
        return
    
    all_rules = collect_rules_for_item(plan_data, item_id)
    matching_rule_info = None
    
    normalized_search = normalize_text(rule)
    
    for rule_info in all_rules:
        r = rule_info['rule']
        full_rule_text = normalize_text(f"[{r['category']}] {r['text']}")
        rule_text_only = normalize_text(r['text'])
        
        if normalized_search in full_rule_text or normalized_search in rule_text_only:
            matching_rule_info = rule_info
            break
    
    if not matching_rule_info:
        click.echo(f"❌ Rule not found matching: {rule}")
        click.echo(f"Available rules for item {item_id} (including inherited):")
        for rule_info in all_rules:
            r = rule_info['rule']
            source_label = f" (from {rule_info['source_title']})" if rule_info['source'] == 'parent' else ""
            click.echo(f"  - [{r['category']}] {r['text']}{source_label}")
        return
    
    # ENFORCEMENT: Check if testable rule requires test evidence
    matching_rule = matching_rule_info['rule']
    is_testable = matching_rule.get('is_testable', False)
    is_strict = matching_rule.get('needs_strict_enforcement', False)
    test_evidence_enabled = get_rule_test_evidence_enabled()
    
    if is_testable and is_strict and test_evidence_enabled:
        test_fields_provided = all([test_name, test_command, test_result, test_file])
        if not test_fields_provided:
            click.echo(f"❌ ERROR: This rule is marked as 🧪 TESTABLE and requires test evidence!")
            click.echo("")
            click.echo(f"Rule: [{matching_rule['category']}] {matching_rule['text']}")
            click.echo("")
            click.echo("This rule needs ALL of these flags:")
            click.echo("  --test-name 'test_function_name'")
            click.echo("  --test-command 'pytest path/to/test.py -v'")
            click.echo("  --test-result pass")
            click.echo("  --test-output 'test output summary'")
            click.echo("  --test-file 'path/to/test.py'")
            click.echo("")
            click.echo("💡 TIP: Generate a test that validates this rule's compliance")
            return
    
    code_blocks = []
    for i in range(len(files)):
        code_block = {
            'file_path': files[i],
            'code_snippet': decode_cli_snippet(snippets[i])
        }
        if line_ranges and i < len(line_ranges):
            code_block['line_range'] = line_ranges[i]
        code_blocks.append(code_block)
    
    verification = {
        'item_id': item_id,
        'explanation': explanation,
        'code_blocks': code_blocks,
        'verdict': verdict,
        'timestamp': datetime.utcnow().isoformat()
    }

    test_fields = [test_name, test_command, test_result, test_output, test_file]
    if any(field is not None for field in test_fields):
        test_code = None
        if test_file:
            from pathlib import Path
            test_path = Path(test_file)
            if test_path.exists():
                try:
                    with open(test_path, 'r', encoding='utf-8') as f:
                        test_code = f.read()
                except Exception as e:
                    click.echo(f"⚠️  Warning: Could not read test file: {e}")
            else:
                click.echo(f"⚠️  Warning: Test file not found: {test_file}")
        
        verification['test_evidence'] = {
            'name': test_name,
            'command': test_command,
            'result': test_result,
            'output': test_output,
            'test_file': test_file,
            'test_code': test_code,
            'enabled': get_rule_test_evidence_enabled()
        }
    
    item = find_item_by_id(plan_data['plan']['items'], item_id)
    if not item:
        click.echo(f"❌ Item {item_id} not found")
        return
    
    if matching_rule_info['is_inherited']:
        inherited_idx = matching_rule_info['inherited_index']
        if 'inherited_rules' not in item:
            item['inherited_rules'] = []
        if inherited_idx < len(item['inherited_rules']):
            if 'verifications' not in item['inherited_rules'][inherited_idx]:
                item['inherited_rules'][inherited_idx]['verifications'] = []
            item['inherited_rules'][inherited_idx]['verifications'].append(verification)
            click.echo(f"✅ Inherited rule verified: [{matching_rule_info['rule']['category']}] {matching_rule_info['rule']['text']}")
        else:
            click.echo(f"❌ Inherited rule index out of bounds")
            return
    else:
        matching_rule = matching_rule_info['rule']
        if 'verifications' not in matching_rule:
            matching_rule['verifications'] = []
        matching_rule['verifications'].append(verification)
        click.echo(f"✅ Own rule verified: [{matching_rule['category']}] {matching_rule['text']}")
    
    _recalculate_inherited_rules(plan_data['plan']['items'])
    
    save_plan_data(chat_id, plan_data)
    
    click.echo(f"📝 Explanation: {explanation[:80]}{'...' if len(explanation) > 80 else ''}")
    click.echo(f"📄 Code blocks: {len(code_blocks)}")
    if 'test_evidence' in verification:
        test_result_label = verification['test_evidence'].get('result') or 'unknown'
        click.echo(f"🧪 Test result: {test_result_label}")
    click.echo(f"✓ Verdict: {verdict}")
