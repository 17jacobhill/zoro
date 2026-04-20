from __future__ import annotations

import subprocess
import re
from typing import Dict, List
from backend.globals.schemas import FileSummary, CodeBlock


def get_git_context(max_chars: int = 12_000) -> str:
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()

        diff = subprocess.run(
            ["git", "diff", "--no-color"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout

        diff = (diff or "")
        if max_chars > 0 and len(diff) > max_chars:
            diff = diff[-max_chars:]

        out_parts: list[str] = []
        if status:
            out_parts.append("git status --porcelain:\n" + status)
        if diff.strip():
            out_parts.append("git diff (truncated):\n" + diff)
        return "\n\n".join(out_parts).strip()
    except Exception:
        return ""


def get_detailed_git_context(max_files: int = 10, max_blocks: int = 5) -> Dict[str, List]:
    try:
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
        
        diff_result = subprocess.run(
            ["git", "diff", "--no-color"],
            capture_output=True,
            text=True,
            check=False,
        )
        
        if status_result.returncode != 0 or diff_result.returncode != 0:
            return {"files_summary": [], "code_blocks": []}
        
        status_lines = status_result.stdout.strip().split('\n')
        diff_text = diff_result.stdout
        
        files_summary: List[FileSummary] = []
        code_blocks: List[CodeBlock] = []
        
        file_stats = _parse_status_for_files(status_lines)
        for file_path, status_code in file_stats[:max_files]:
            stats = _get_file_stats_from_diff(diff_text, file_path)
            summary = _generate_file_summary(file_path, status_code, stats)
            files_summary.append(FileSummary(
                path=file_path,
                summary=summary,
                lines=stats.get('lines', '+0 -0')
            ))
        
        blocks = _extract_code_blocks(diff_text, max_blocks)
        for block in blocks:
            code_blocks.append(CodeBlock(
                file=block['file'],
                before=block['before'],
                after=block['after'],
                lines=block['lines']
            ))
        
        return {
            "files_summary": [f.model_dump() for f in files_summary],
            "code_blocks": [b.model_dump() for b in code_blocks]
        }
        
    except Exception:
        return {"files_summary": [], "code_blocks": []}


def _parse_status_for_files(status_lines: List[str]) -> List[tuple]:
    files = []
    for line in status_lines:
        if not line.strip():
            continue
        status_code = line[:2]
        file_path = line[3:].strip()
        files.append((file_path, status_code))
    return files


def _get_file_stats_from_diff(diff_text: str, file_path: str) -> Dict[str, str]:
    pattern = rf'diff --git a/{re.escape(file_path)} b/{re.escape(file_path)}.*?(?=diff --git|$)'
    match = re.search(pattern, diff_text, re.DOTALL)
    
    if not match:
        return {"lines": "+0 -0"}
    
    file_diff = match.group(0)
    added = len(re.findall(r'^\+[^+]', file_diff, re.MULTILINE))
    removed = len(re.findall(r'^-[^-]', file_diff, re.MULTILINE))
    
    return {"lines": f"+{added} -{removed}"}


def _generate_file_summary(file_path: str, status_code: str, stats: Dict[str, str]) -> str:
    if status_code.startswith('A'):
        return "New file created"
    elif status_code.startswith('M'):
        return "Modified"
    elif status_code.startswith('D'):
        return "Deleted"
    elif status_code.startswith('R'):
        return "Renamed"
    else:
        return "Changed"


def _extract_code_blocks(diff_text: str, max_blocks: int) -> List[Dict[str, str]]:
    blocks = []
    
    file_diffs = re.split(r'diff --git ', diff_text)[1:]
    
    for file_diff in file_diffs[:max_blocks]:
        file_match = re.match(r'a/(.*?) b/(.*?)\n', file_diff)
        if not file_match:
            continue
        
        file_path = file_match.group(1)
        
        hunks = re.finditer(r'@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@[^\n]*\n(.*?)(?=@@|$)', file_diff, re.DOTALL)
        
        for hunk in hunks:
            start_line = hunk.group(2)
            hunk_content = hunk.group(3)
            
            before_lines = []
            after_lines = []
            
            for line in hunk_content.split('\n')[:20]:
                if line.startswith('-') and not line.startswith('---'):
                    before_lines.append(line[1:])
                elif line.startswith('+') and not line.startswith('+++'):
                    after_lines.append(line[1:])
                elif line.startswith(' '):
                    before_lines.append(line[1:])
                    after_lines.append(line[1:])
            
            if before_lines or after_lines:
                blocks.append({
                    'file': file_path,
                    'before': '\n'.join(before_lines[:10]),
                    'after': '\n'.join(after_lines[:10]),
                    'lines': f"{start_line}-{int(start_line) + len(after_lines)}"
                })
            
            if len(blocks) >= max_blocks:
                return blocks
    
    return blocks
