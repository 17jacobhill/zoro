import click
from datetime import datetime
from backend.visualization.services.plan_tracker import (
    load_plan_data,
    save_plan_data,
    get_chat_id_from_plan_md,
    find_item_by_id
)


def decode_cli_snippet(snippet: str) -> str:
    return (
        snippet
        .replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\r", "\r")
    )


@click.command()
@click.argument('item_id')
@click.option('--explanation', required=True, help='Detailed explanation of what was accomplished')
@click.option('--file', 'files', multiple=True, help='File path (can be repeated)')
@click.option('--snippet', 'snippets', multiple=True, help='Code snippet (can be repeated). Use escaped \\n for multiline evidence.')
@click.option('--line-range', 'line_ranges', multiple=True, help='Line range (optional, can be repeated)')
@click.option('--output', default=None, help='Output file/URL showing result')
@click.option('--verdict', type=click.Choice(['pass', 'fail', 'unclear']), default='pass')
@click.option('--chat-id', default=None, help='Chat ID (auto-detect if not provided)')
def viz_verify_step(item_id, explanation, files, snippets, line_ranges, output, verdict, chat_id):
    if not chat_id:
        chat_id = get_chat_id_from_plan_md()
        if not chat_id:
            click.echo("❌ No active visualization plan found")
            return
    
    if files and len(files) != len(snippets):
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
    
    code_blocks = []
    if files:
        for i in range(len(files)):
            code_block = {
                'file_path': files[i],
                'code_snippet': decode_cli_snippet(snippets[i])
            }
            if line_ranges and i < len(line_ranges):
                code_block['line_range'] = line_ranges[i]
            code_blocks.append(code_block)
    
    verification = {
        'explanation': explanation,
        'code_blocks': code_blocks,
        'verdict': verdict,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if output:
        verification['output'] = output
    
    has_children = 'children' in item and len(item.get('children', [])) > 0
    
    if has_children:
        if 'item_verifications' not in item:
            item['item_verifications'] = []
        item['item_verifications'].append(verification)
        verification_type = "item"
    else:
        if 'step_verifications' not in item:
            item['step_verifications'] = []
        item['step_verifications'].append(verification)
        verification_type = "step"
    
    save_plan_data(chat_id, plan_data)
    
    click.echo(f"✅ {verification_type.capitalize()} verified: {item['title']}")
    click.echo(f"📝 Explanation: {explanation[:80]}{'...' if len(explanation) > 80 else ''}")
    if code_blocks:
        click.echo(f"📄 Code blocks: {len(code_blocks)}")
    if output:
        click.echo(f"📂 Output: {output}")
    click.echo(f"✓ Verdict: {verdict}")
