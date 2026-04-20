from typing import List, Optional, Dict
from pydantic import BaseModel, Field, ConfigDict


class CodeBlock(BaseModel):
    file_path: str = Field(..., description="Path to the file containing this code")
    code_snippet: str = Field(..., description="Literal code from the file")
    line_range: Optional[str] = Field(default=None, description="Line range (e.g., '10-45')")
    
    model_config = ConfigDict(extra="forbid")


class TestEvidence(BaseModel):
    name: str = Field(..., description="Test name (e.g., 'test_repository_pattern')")
    command: str = Field(..., description="Command used to run the test")
    result: str = Field(..., description="pass | fail | error")
    output: str = Field(..., description="Test output summary (stdout/stderr)")
    test_file: str = Field(..., description="Path to test file")
    test_code: Optional[str] = Field(default=None, description="Actual test code contents")
    enabled: bool = Field(..., description="Whether test evidence feature is enabled")
    
    model_config = ConfigDict(extra="forbid")


class RuleVerification(BaseModel):
    explanation: str = Field(..., description="Detailed natural language explanation of how the rule was followed, grounded in specific implementation details")
    code_blocks: List[CodeBlock] = Field(..., description="Code evidence from one or more files")
    verdict: str = Field(..., description="pass | fail | unclear")
    timestamp: str = Field(..., description="ISO timestamp")
    test_evidence: Optional[TestEvidence] = Field(default=None, description="Optional test evidence for this rule")
    
    model_config = ConfigDict(extra="forbid")


class StepVerification(BaseModel):
    explanation: str = Field(..., description="Detailed explanation of what was accomplished and how, with specific evidence")
    code_blocks: List[CodeBlock] = Field(default_factory=list, description="Code evidence from one or more files")
    output: Optional[str] = Field(default=None, description="File/URL showing result")
    verdict: str = Field(..., description="pass | fail | unclear")
    timestamp: str = Field(..., description="ISO timestamp")
    
    model_config = ConfigDict(extra="forbid")


class Rule(BaseModel):
    category: str = Field(..., description="Rule category")
    text: str = Field(..., description="Rule text")
    context: Optional[str] = Field(default=None, description="Rule context")
    evidence: Optional[str] = Field(default=None, description="Rule evidence")
    confidence: float = Field(default=0.5, description="Confidence score 0-1")
    decay: float = Field(default=0.5, description="Decay score 0-1")
    confidence_reasoning: Optional[str] = Field(default=None, description="Why this confidence")
    decay_reasoning: Optional[str] = Field(default=None, description="Why this decay")
    reasoning: Optional[str] = Field(default=None, description="Detailed explanation of why this rule matches this plan item")
    context_match: Optional[float] = Field(default=None, description="Score 0-1 indicating how well rule context matches plan item")
    relevance_score: Optional[float] = Field(default=None, description="Overall relevance score 0-1")
    verifications: List[RuleVerification] = Field(default_factory=list, description="List of verifications for this rule")
    needs_strict_enforcement: bool = Field(default=False, description="Whether CLI must verify this rule")
    is_testable: bool = Field(default=False, description="Whether this rule requires automated test evidence")
    kb_item_id: Optional[str] = Field(default=None, description="KB item ID if from favorites")
    
    model_config = ConfigDict(extra="forbid")


class RuleConflict(BaseModel):
    conflict_id: str = Field(..., description="Unique stable identifier for this conflict")
    rule_item_ids: List[str] = Field(..., description="Plan item IDs where conflicting rules both apply")
    rule_indices: Dict[str, List[int]] = Field(default_factory=dict, description="Map of item_id -> list of rule indices that are in conflict")
    explanation: str = Field(..., description="Clear description of why these rules conflict")
    severity: str = Field(..., description="low | medium | high - impact level of the conflict")
    resolved: bool = Field(default=False, description="Whether this conflict has been resolved")
    chosen_rule_index: Optional[int] = Field(default=None, description="Index of the rule that was chosen (if resolved)")
    resolved_at: Optional[str] = Field(default=None, description="ISO timestamp when resolved")
    
    model_config = ConfigDict(extra="forbid")


class InheritedRule(BaseModel):
    rule: Rule = Field(..., description="The inherited rule")
    source: str = Field(..., description="Title of the parent item this rule comes from")
    
    model_config = ConfigDict(extra="forbid")


class PlanItem(BaseModel):
    id: str = Field(..., description="Unique item identifier")
    number: str = Field(..., description="Item number (e.g., '1', 'Phase 1', '2.1')")
    title: str = Field(..., description="Item title")
    description: str = Field(default="", description="Detailed description")
    children: List['PlanItem'] = Field(default_factory=list, description="Nested items")
    rules: List[Rule] = Field(default_factory=list, description="Rules to follow for this item")
    inherited_rules: List[InheritedRule] = Field(default_factory=list, description="Rules inherited from parent items")
    conflicts: List[RuleConflict] = Field(default_factory=list, description="Rule conflicts for this item")
    has_unresolved_conflicts: bool = Field(default=False, description="Whether this item has unresolved rule conflicts")
    step_verifications: List[StepVerification] = Field(default_factory=list, description="Step-level verifications (for leaf items)")
    item_verifications: List[StepVerification] = Field(default_factory=list, description="Item-level verifications (for non-leaf items)")
    
    model_config = ConfigDict(extra="forbid")


class ExtractedPlan(BaseModel):
    has_plan: bool = Field(..., description="Whether a plan was found")
    structure_type: str = Field(..., description="Plan structure type")
    plan: dict = Field(default_factory=dict, description="Extracted plan data")
    
    model_config = ConfigDict(extra="forbid")


class VizRequirement(BaseModel):
    id: str = Field(..., description="Unique requirement identifier")
    text: str = Field(..., description="Requirement text")
    created_at: str = Field(..., description="ISO timestamp")
    
    model_config = ConfigDict(extra="forbid")


class VizRequirementVerification(BaseModel):
    requirement_id: str = Field(..., description="Reference to requirement")
    verdict: str = Field(..., description="pass | fail | unclear")
    evidence: str = Field(..., description="Evidence text")
    context: str = Field(..., description="Context of what was being built")
    timestamp: str = Field(..., description="ISO timestamp")
    
    model_config = ConfigDict(extra="forbid")


class VizEnforcementRecord(BaseModel):
    chat_id: str = Field(..., description="Chat identifier")
    item_id: str = Field(..., description="Plan item identifier")
    requirements: List[VizRequirement] = Field(default_factory=list, description="List of requirements")
    verifications: List[VizRequirementVerification] = Field(default_factory=list, description="List of verifications")
    
    model_config = ConfigDict(extra="forbid")
