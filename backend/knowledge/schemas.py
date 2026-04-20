from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Literal


class KnowledgeItem(BaseModel):
    item_id: str = Field(..., description="Unique identifier (UUID)")
    type: Literal["rule", "doc"] = Field(..., description="Rule vs general documentation")
    category: str = Field(..., description="Category name (e.g., workflow, architecture, meta)")
    title: str = Field(..., description="Short descriptive title (5-8 words)")
    content: str = Field(..., description="The actual rule text or doc content")
    context: Optional[str] = Field(None, description="What was being built (for rules)")
    evidence: Optional[str] = Field(None, description="Supporting quotes (for rules)")
    source_file: str = Field(..., description="Original filename (e.g., dynamic_reflection.md)")
    usage_count: int = Field(default=0, description="Times used in plans")
    is_favorite: bool = Field(default=False, description="User favorited")
    is_strict: bool = Field(default=False, description="Should be strictly enforced when added to plan")
    is_testable: bool = Field(default=False, description="Requires automated test evidence when used in plans")
    confidence: float = Field(default=0.5, description="Confidence score 0-1")
    decay: float = Field(default=0.5, description="Decay/specificity score 0-1")
    confidence_reasoning: Optional[str] = Field(None, description="Confidence explanation")
    decay_reasoning: Optional[str] = Field(None, description="Decay explanation")
    created_at: str = Field(..., description="ISO timestamp")
    
    model_config = ConfigDict(extra="forbid")


class Category(BaseModel):
    category_id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Category name (e.g., workflow, meta)")
    description: str = Field(..., description="What this category covers")
    color: str = Field(..., description="Hex color for UI display")
    item_count: int = Field(default=0, description="Number of items in category")
    is_system: bool = Field(default=True, description="System vs user-created")
    created_at: str = Field(..., description="ISO timestamp")
    
    model_config = ConfigDict(extra="forbid")


class KnowledgeBase(BaseModel):
    items: List[KnowledgeItem] = Field(default_factory=list)
    categories: List[Category] = Field(default_factory=list)
    
    model_config = ConfigDict(extra="forbid")


class ProcessingLog(BaseModel):
    files: dict = Field(default_factory=dict, description="Map of filename -> processing metadata")
    
    model_config = ConfigDict(extra="forbid")


class MergeSuggestion(BaseModel):
    suggestion_id: str = Field(..., description="Unique ID")
    merge_from: List[str] = Field(..., description="Categories to merge")
    merge_to: str = Field(..., description="Target category")
    reasoning: str = Field(..., description="Why merge these")
    dismissed: bool = Field(default=False, description="User dismissed")
    
    model_config = ConfigDict(extra="forbid")


class DuplicateSuggestion(BaseModel):
    suggestion_id: str = Field(..., description="Unique ID")
    item_ids: List[str] = Field(..., description="Duplicate item IDs")
    similarity_score: float = Field(..., description="0-1 similarity")
    reasoning: str = Field(..., description="Why duplicates")
    suggested_merged: str = Field(..., description="Proposed merged content")
    dismissed: bool = Field(default=False, description="User dismissed")
    
    model_config = ConfigDict(extra="forbid")
