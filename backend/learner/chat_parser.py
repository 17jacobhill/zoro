from __future__ import annotations
import uuid
import json
import re
import tiktoken
from typing import List, Dict, Any, Optional
from pathlib import Path
from backend.globals.models import get_default_provider
from backend.utils import get_project_root
from backend.learner.prompts.chat_parser import TASK_LABELING_PROMPT


class ChatParser:
    
    TOOL_PREFIXES = (
        "<read_file",
        "<ask_followup_question",
        "<tool",
        "[read_file",
        "Tool [",
    )
    
    SYSTEM_PREFIXES = (
        "<environment_details",
        "# Todo List",
        "# TODO LIST",
        "# Visual Studio",
        "# Current Time",
        "# Current Mode",
        "# Context Window",
    )
    
    def __init__(self, model: Optional[str] = None, debug: bool = False, logger: Optional[callable] = None, max_task_tokens: int = 200_000) -> None:
        self._model = model or "gpt-5"
        self._debug = debug
        self._provider = get_default_provider()
        self._logger = logger or print
        self._max_task_tokens = max_task_tokens
    
    def _is_human_user_block(self, text: str) -> bool:
        t = text.strip()
        
        if "<task>" in t or "<user_message>" in t:
            return True
        
        if t.startswith(self.TOOL_PREFIXES) or t.startswith(self.SYSTEM_PREFIXES):
            return False
        
        if len(t.splitlines()) > 30 and "import " in t:
            return False
        
        if t.startswith("[read_file"):
            return False
        
        if not t or t.isspace():
            return False
        
        return True
    
    def _extract_inner_wrapped(self, text: str) -> str:
        m = re.search(r"<task>(.*?)</task>", text, flags=re.S)
        if m:
            return m.group(1).strip()
        
        m = re.search(r"<user_message>(.*?)</user_message>", text, flags=re.S)
        if m:
            return m.group(1).strip()
        
        return text.strip()
    
    def _create_supervision_cleaned_json(self, json_data: List[Dict]) -> List[Dict]:
        # Check if messages are already in plain format (no special tags)
        is_already_cleaned = not any(
            "<task>" in block.get("text", "") or "<user_message>" in block.get("text", "")
            for msg in json_data
            if msg.get("role") == "user"
            for block in msg.get("content", [])
            if block.get("type") == "text"
        )

        if is_already_cleaned:
            return json_data

        cleaned = []

        for msg in json_data:
            role = msg.get("role")
            content = msg.get("content", [])
            
            if role == "user":
                cleaned_blocks = []
                for block in content:
                    if block.get("type") != "text":
                        continue
                    
                    text = block.get("text", "")
                    
                    if "<task>" in text or "<user_message>" in text:
                        cleaned_text = self._extract_inner_wrapped(text)
                        cleaned_blocks.append({"type": "text", "text": cleaned_text})
                
                if cleaned_blocks:
                    cleaned.append({"role": "user", "content": cleaned_blocks})
            
            elif role == "assistant":
                cleaned_blocks = []
                for block in content:
                    if block.get("type") == "thinking":
                        continue
                    
                    if block.get("type") == "tool_use":
                        tool_name = block.get("name", "")
                        input_data = block.get("input", {})
                        
                        if tool_name == "write_to_file":
                            path = input_data.get("path", "unknown")
                            content_full = input_data.get("content", "")
                            lines = content_full.split('\n')
                            snippet = '\n'.join(lines[:20]) if len(lines) > 20 else content_full
                            if len(lines) > 20:
                                snippet += f"\n... ({len(lines) - 20} more lines)"
                            
                            summary = f"[WRITE_FILE] {path}\n```\n{snippet}\n```"
                            cleaned_blocks.append({"type": "text", "text": summary})
                        
                        elif tool_name == "execute_command":
                            command = input_data.get("command", "unknown")
                            summary = f"[EXECUTE_COMMAND] {command}"
                            cleaned_blocks.append({"type": "text", "text": summary})
                        
                        elif tool_name == "read_file":
                            path = input_data.get("path", "unknown")
                            summary = f"[READ_FILE] {path}"
                            cleaned_blocks.append({"type": "text", "text": summary})
                        
                        elif tool_name == "replace_in_file":
                            path = input_data.get("path", "unknown")
                            diff = input_data.get("diff", "")
                            lines = diff.split('\n')
                            snippet = '\n'.join(lines[:30]) if len(lines) > 30 else diff
                            if len(lines) > 30:
                                snippet += f"\n... ({len(lines) - 30} more lines)"
                            
                            summary = f"[REPLACE_IN_FILE] {path}\n```\n{snippet}\n```"
                            cleaned_blocks.append({"type": "text", "text": summary})
                        
                        elif tool_name == "plan_mode_respond":
                            response_text = input_data.get("response", "").strip()
                            if response_text:
                                cleaned_blocks.append({"type": "text", "text": response_text})
                        
                        continue
                    
                    if block.get("type") == "text":
                        t = block.get("text", "").strip()
                        
                        if t.startswith(self.TOOL_PREFIXES):
                            continue
                        
                        if "<environment_details>" in t:
                            continue
                        
                        if t.startswith(self.SYSTEM_PREFIXES):
                            continue
                        
                        cleaned_blocks.append(block)
                
                if cleaned_blocks:
                    cleaned.append({"role": "assistant", "content": cleaned_blocks})
        
        return cleaned
    
    def _clean_json_messages(self, json_data: List[Dict]) -> List[Dict]:
        is_already_cleaned = not any(
            "<task>" in block.get("text", "") or "<user_message>" in block.get("text", "")
            for msg in json_data
            if msg.get("role") == "user"
            for block in msg.get("content", [])
            if block.get("type") == "text"
        )

        if is_already_cleaned:
            return json_data

        cleaned = []
        
        for msg in json_data:
            role = msg.get("role")
            content = msg.get("content", [])
            
            if role == "user":
                cleaned_blocks = []
                for block in content:
                    if block.get("type") != "text":
                        continue
                    
                    text = block.get("text", "")
                    
                    if "<task>" in text or "<user_message>" in text:
                        cleaned_text = self._extract_inner_wrapped(text)
                        cleaned_blocks.append({
                            "type": "text",
                            "text": cleaned_text
                        })
                
                if cleaned_blocks:
                    cleaned.append({
                        "role": "user",
                        "content": cleaned_blocks
                    })
            
            elif role == "assistant":
                cleaned_blocks = []
                for block in content:
                    if block.get("type") == "thinking":
                        thinking_block = {
                            "type": "thinking",
                            "thinking": block.get("thinking", "")
                        }
                        cleaned_blocks.append(thinking_block)
                        continue
                    
                    # Handle tool_use blocks (Gemini format)
                    if block.get("type") == "tool_use":
                        tool_name = block.get("name", "")
                        input_data = block.get("input", {})
                        
                        if tool_name == "write_to_file":
                            path = input_data.get("path", "unknown")
                            content_full = input_data.get("content", "")
                            lines = content_full.split('\n')
                            snippet = '\n'.join(lines[:20]) if len(lines) > 20 else content_full
                            if len(lines) > 20:
                                snippet += f"\n... ({len(lines) - 20} more lines)"
                            
                            summary = f"[WRITE_FILE] {path}\n```\n{snippet}\n```"
                            cleaned_blocks.append({"type": "text", "text": summary})
                        
                        elif tool_name == "execute_command":
                            command = input_data.get("command", "unknown")
                            summary = f"[EXECUTE_COMMAND] {command}"
                            cleaned_blocks.append({"type": "text", "text": summary})
                        
                        elif tool_name == "read_file":
                            path = input_data.get("path", "unknown")
                            summary = f"[READ_FILE] {path}"
                            cleaned_blocks.append({"type": "text", "text": summary})
                        
                        elif tool_name == "replace_in_file":
                            path = input_data.get("path", "unknown")
                            diff = input_data.get("diff", "")
                            lines = diff.split('\n')
                            snippet = '\n'.join(lines[:30]) if len(lines) > 30 else diff
                            if len(lines) > 30:
                                snippet += f"\n... ({len(lines) - 30} more lines)"
                            
                            summary = f"[REPLACE_IN_FILE] {path}\n```\n{snippet}\n```"
                            cleaned_blocks.append({"type": "text", "text": summary})
                        
                        elif tool_name == "plan_mode_respond":
                            response_text = input_data.get("response", "").strip()
                            task_progress = input_data.get("task_progress", "").strip()
                            
                            # Combine with clear separation - detailed response first, then checklist
                            parts = []
                            if response_text:
                                parts.append(response_text)
                            if task_progress:
                                parts.append(f"Progress Checklist:\n{task_progress}")
                            
                            combined_text = "\n\n".join(parts)
                            
                            if combined_text:
                                cleaned_blocks.append({
                                    "type": "text",
                                    "text": combined_text
                                })
                        
                        continue
                    
                    if block.get("type") == "text":
                        t = block.get("text", "").strip()
                        
                        # Skip if starts with tool XML tags
                        if t.startswith(self.TOOL_PREFIXES):
                            continue
                        
                        # Skip if contains environment details block
                        if "<environment_details>" in t:
                            continue
                        
                        # ALWAYS keep if contains plan-related markers
                        plan_markers = [
                            "[plan_mode_respond]",
                            "- [ ]", "- [x]",  # Checklist items
                            "## Phase", "### Step", "#### ", "Step ",  # Plan structure
                            "# Plan", "## Plan",  # Plan titles
                            "Phase 1", "Phase 2", "Phase 3",  # Phase mentions
                            "Checklist:", "TODO:", "To do:",  # Task lists
                            "Implementation Plan", "Strategy", "Approach"  # Plan keywords
                        ]
                        if any(marker in t for marker in plan_markers):
                            cleaned_blocks.append(block)
                            continue
                        
                        # Skip if starts with system prefixes (but not if it's in the middle of text)
                        if t.startswith(self.SYSTEM_PREFIXES):
                            continue
                        
                        # Keep all other text blocks
                        cleaned_blocks.append(block)
                
                if cleaned_blocks:
                    cleaned.append({
                        "role": "assistant",
                        "content": cleaned_blocks
                    })
        
        return cleaned
    
    def _extract_user_messages_from_json(self, json_data: List[Dict]) -> List[Dict[str, Any]]:
        messages = []
        msg_num = 0
        
        for msg in json_data:
            if msg.get("role") == "user":
                for block in msg.get("content", []):
                    if block.get("type") == "text":
                        text = block.get("text", "").strip()
                        if text:
                            msg_num += 1
                            messages.append({
                                'line_num': msg_num,
                                'text': text
                            })
        
        return messages
    
    def _extract_user_messages(self, md_text: str) -> List[Dict[str, Any]]:
        lines = md_text.split('\n')
        messages = []
        
        in_task = False
        in_user_message = False
        current_message = []
        start_line = 0
        
        for i, line in enumerate(lines, 1):
            line_lower = line.lower().strip()
            
            if line_lower == '<task>':
                in_task = True
                start_line = i
                current_message = []
                continue
            
            if line_lower == '<user_message>':
                in_user_message = True
                start_line = i
                current_message = []
                continue
            
            if line_lower == '</task>':
                in_task = False
                if current_message:
                    text = ' '.join(current_message).strip()
                    if text:
                        messages.append({
                            'line_num': start_line,
                            'text': text
                        })
                current_message = []
                continue
            
            if line_lower == '</user_message>':
                in_user_message = False
                if current_message:
                    text = ' '.join(current_message).strip()
                    if text:
                        messages.append({
                            'line_num': start_line,
                            'text': text
                        })
                current_message = []
                continue
            
            if (in_task or in_user_message) and line.strip():
                current_message.append(line.strip())
        
        return messages
    
    def _label_messages_with_llm(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        message_list = []
        for i, msg in enumerate(messages):
            prefix = "[INITIAL TASK]" if i == 0 else "[FOLLOW-UP]"
            text = msg['text'][:200]
            message_list.append(f"{i+1}. {prefix} (line {msg['line_num']}): \"{text}...\"")
        
        prompt = TASK_LABELING_PROMPT.format(messages=chr(10).join(message_list))

        response = self._provider.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model=self._model
        )
        
        labels = json.loads(response)
        return labels
    
    def _group_into_tasks(
        self, 
        md_text: str, 
        messages: List[Dict[str, Any]], 
        labels: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        lines = md_text.split('\n')
        
        task_boundaries = {}
        for label in labels:
            msg_num = label['message_num'] - 1
            task_num = label['task']
            
            if msg_num < 0 or msg_num >= len(messages):
                continue
            
            if task_num not in task_boundaries:
                task_boundaries[task_num] = {
                    'start_line': messages[msg_num]['line_num'],
                    'end_line': None,
                    'description': messages[msg_num]['text']
                }
            
            next_msg_idx = msg_num + 1
            if next_msg_idx < len(messages):
                next_label = next((l for l in labels if l['message_num'] == next_msg_idx + 1), None)
                if next_label and next_label['task'] != task_num:
                    task_boundaries[task_num]['end_line'] = messages[next_msg_idx]['line_num'] - 1
            else:
                task_boundaries[task_num]['end_line'] = len(lines)
        
        tasks = []
        for task_num in sorted(task_boundaries.keys()):
            boundary = task_boundaries[task_num]
            start = boundary['start_line'] - 1
            end = boundary['end_line'] if boundary['end_line'] else len(lines)
            
            raw_data = '\n'.join(lines[start:end])
            
            tasks.append({
                'task_id': str(uuid.uuid4()),
                'description': boundary['description'][:200],
                'raw_data': raw_data
            })
        
        return tasks
    
    def _estimate_tokens(self, text: str) -> int:
        try:
            encoding = tiktoken.encoding_for_model("gpt-4")
            return len(encoding.encode(text))
        except Exception:
            return len(text) // 4
    
    def _split_oversized_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        final_tasks = []
        
        for task in tasks:
            tokens = self._estimate_tokens(task['raw_data'])
            
            if tokens <= self._max_task_tokens:
                final_tasks.append(task)
            else:
                if self._debug:
                    self._logger(f"\n⚠️  Task exceeds limit ({tokens:,} tokens), re-parsing recursively...")
                
                subtasks = self.parse(task['raw_data'])
                
                if self._debug:
                    self._logger(f"   Split into {len(subtasks)} subtasks")
                
                final_tasks.extend(subtasks)
        
        return final_tasks
    
    def parse(self, md_text: str) -> List[Dict[str, Any]]:
        first_task_idx = md_text.lower().find('<task>')
        if first_task_idx > 0:
            md_text = md_text[first_task_idx:]
        
        messages = self._extract_user_messages(md_text)
        
        if not messages:
            return []
        
        if self._debug:
            self._logger(f"\n=== EXTRACTED {len(messages)} USER MESSAGES ===")
            for i, msg in enumerate(messages):
                msg_type = "TASK" if i == 0 else "FOLLOW-UP"
                self._logger(f"{i+1}. [{msg_type}] Line {msg['line_num']}: {msg['text'][:80]}...")
            self._logger("")
        
        labels = self._label_messages_with_llm(messages)
        
        if self._debug:
            self._logger(f"=== LLM LABELS ===")
            for label in labels:
                msg_num = label['message_num'] - 1
                task_num = label['task']
                if 0 <= msg_num < len(messages):
                    msg_text = messages[msg_num]['text'][:60]
                    self._logger(f"Message {label['message_num']} → Task {task_num}: \"{msg_text}...\"")
            self._logger("")
        
        tasks = self._group_into_tasks(md_text, messages, labels)
        
        return self._split_oversized_tasks(tasks)
    
    def parse_json(self, json_data: List[Dict], source_file: Optional[str] = None) -> List[Dict[str, Any]]:
        cleaned_json = self._clean_json_messages(json_data)
        
        if source_file:
            cleaned_dir = get_project_root() / ".zoro" / "chat_history" / "cleaned"
            cleaned_dir.mkdir(parents=True, exist_ok=True)
            cleaned_path = cleaned_dir / Path(source_file).name
            
            with open(cleaned_path, 'w', encoding='utf-8') as f:
                json.dump(cleaned_json, f, indent=2)
            
            self._logger(f"✓ Saved cleaned JSON to {cleaned_path}")
        
        messages = self._extract_user_messages_from_json(cleaned_json)
        
        if not messages:
            self._logger("⚠️  No user messages extracted from JSON")
            return []
        
        self._logger(f"\n=== EXTRACTED {len(messages)} USER MESSAGES FROM JSON ===")
        for i, msg in enumerate(messages):
            msg_type = "TASK" if i == 0 else "FOLLOW-UP"
            self._logger(f"{i+1}. [{msg_type}]: {msg['text'][:80]}...")
        self._logger("")
        
        labels = self._label_messages_with_llm(messages)
        
        self._logger(f"=== LLM LABELS ===")
        for label in labels:
            msg_num = label['message_num'] - 1
            task_num = label['task']
            if 0 <= msg_num < len(messages):
                msg_text = messages[msg_num]['text'][:60]
                self._logger(f"Message {label['message_num']} → Task {task_num}: \"{msg_text}...\"")
        self._logger("")
        
        msg_to_task = {label['message_num']: label['task'] for label in labels}
        
        tasks = []
        for task_num in sorted(set(label['task'] for label in labels)):
            task_msg_nums = {label['message_num'] for label in labels if label['task'] == task_num}
            
            min_msg = min(task_msg_nums)
            max_msg = max(task_msg_nums)
            
            task_json = []
            current_msg_num = 0
            in_task_range = False
            
            for msg in cleaned_json:
                if msg['role'] == 'user':
                    current_msg_num += 1
                    
                    if current_msg_num == min_msg:
                        in_task_range = True
                    elif current_msg_num > max_msg:
                        in_task_range = False
                    
                    if current_msg_num in task_msg_nums:
                        task_json.append(msg)
                
                elif msg['role'] == 'assistant' and in_task_range:
                    task_json.append(msg)
            
            description = messages[min(task_msg_nums) - 1]['text'][:200]
            tasks.append({
                'task_id': str(uuid.uuid4()),
                'description': description,
                'raw_data': json.dumps(task_json, indent=2)
            })
        
        self._logger(f"✓ Generated {len(tasks)} task(s)\n")
        
        return self._split_oversized_tasks(tasks)
    
    def parse_file(self, file_path: str) -> List[Dict[str, Any]]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if path.suffix == '.json':
            with open(path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            return self.parse_json(json_data, source_file=str(path))
        else:
            with open(path, 'r', encoding='utf-8') as f:
                return self.parse(f.read())
