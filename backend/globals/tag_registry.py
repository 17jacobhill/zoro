from __future__ import annotations
import json
from pathlib import Path
from typing import List, Dict, Optional
from backend.utils import get_project_root


class TagRegistry:
    def __init__(self, registry_file: str = "chat_tags.json"):
        self._project_root = get_project_root()
        self._registry_path = self._project_root / ".zoro" / "generated" / registry_file
    
    def _load(self) -> Dict[str, List[str]]:
        if not self._registry_path.exists():
            return {}
        
        with open(self._registry_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data.get('chat_tags', {})
    
    def _save(self, chat_tags: Dict[str, List[str]]):
        self._registry_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {'chat_tags': chat_tags}
        with open(self._registry_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    def _normalize_tag(self, tag: str) -> str:
        return tag.strip().lower()
    
    def add_tags(self, chat_name: str, tags: List[str]):
        chat_tags = self._load()
        
        if chat_name not in chat_tags:
            chat_tags[chat_name] = []
        
        existing = set(chat_tags[chat_name])
        normalized_tags = [self._normalize_tag(tag) for tag in tags if tag.strip()]
        
        for tag in normalized_tags:
            if tag not in existing:
                chat_tags[chat_name].append(tag)
        
        chat_tags[chat_name] = sorted(set(chat_tags[chat_name]))
        self._save(chat_tags)
    
    def remove_tags(self, chat_name: str, tags: List[str]):
        chat_tags = self._load()
        
        if chat_name not in chat_tags:
            return
        
        normalized_tags = {self._normalize_tag(tag) for tag in tags if tag.strip()}
        
        chat_tags[chat_name] = [
            tag for tag in chat_tags[chat_name]
            if tag not in normalized_tags
        ]
        
        if not chat_tags[chat_name]:
            del chat_tags[chat_name]
        
        self._save(chat_tags)
    
    def get_tags(self, chat_name: str) -> List[str]:
        chat_tags = self._load()
        return chat_tags.get(chat_name, [])
    
    def list_all_tags(self) -> Dict[str, int]:
        chat_tags = self._load()
        
        tag_counts = {}
        for tags in chat_tags.values():
            for tag in tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        return dict(sorted(tag_counts.items()))
    
    def get_chats_by_tags(self, tags: List[str]) -> List[str]:
        if not tags:
            return []
        
        chat_tags = self._load()
        normalized_filter_tags = {self._normalize_tag(tag) for tag in tags if tag.strip()}
        
        matching_chats = []
        for chat_name, chat_tag_list in chat_tags.items():
            chat_tag_set = set(chat_tag_list)
            if chat_tag_set & normalized_filter_tags:
                matching_chats.append(chat_name)
        
        return sorted(matching_chats)
