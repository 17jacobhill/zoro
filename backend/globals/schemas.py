from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


class Task(BaseModel):
    task_id: str = Field(..., description="Unique identifier for the task")
    description: str = Field(..., description="Description of what the task is")
    raw_data: str = Field(..., description="Raw input/data for the task")
    suggested_type: Optional[str] = Field(None, description="Task type suggested by categorizer")
    messages: Optional[List[str]] = Field(None, description="Parsed user messages from chat")

    model_config = ConfigDict(extra="forbid")


class Rule(BaseModel):
    rule_id: str = Field(..., description="Unique identifier for the rule")
    rule: str = Field(
        ..., 
        description="The rule text explaining how to complete tasks faster/better"
    )
    task_id: str = Field(
        ..., 
        description="Reference to the task this rule was learned from"
    )
    task_description: str = Field(
        ..., 
        description="Brief description of the task this was learned from"
    )
    reasoning: str = Field(
        ...,
        description=(
            "Detailed analysis of the trajectory: what outputs were liked vs disliked, "
            "how the conversation evolved, and why the rule would shorten future iterations"
        )
    )
    confidence: int = Field(
        ..., 
        ge=1, 
        le=10,
        description="Confidence score from 1 (low) to 10 (high)"
    )
    decay: int = Field(
        ..., 
        ge=1, 
        le=10,
        description="Decay score from 1 (low) to 10 (high)"
    )
    index: Optional[int] = Field(
        None, 
        description="Optional index for ordering rules"
    )

    model_config = ConfigDict(extra="forbid")


class LearningRulesDB(BaseModel):
    rules: List[Rule] = Field(
        default_factory=list,
        description="List of learned rules"
    )

    model_config = ConfigDict(extra="forbid")


class TaskDB(BaseModel):
    tasks: List[Task] = Field(
        default_factory=list,
        description="List of all tasks"
    )

    model_config = ConfigDict(extra="forbid")


# V2 Learning System Schemas

class RuleV2(BaseModel):
    rule_id: str = Field(..., description="Unique identifier for the rule")
    rule: str = Field(..., description="The rule text")
    reasoning: Optional[str] = Field(None, description="Detailed evidence and examples")
    confidence: Optional[int] = Field(None, ge=1, le=10, description="Confidence score 1-10")
    decay: Optional[int] = Field(None, ge=1, le=10, description="Decay score 1-10")
    from_task_id: Optional[str] = Field(None, description="Source task ID")
    
    model_config = ConfigDict(extra="forbid")


class AnalyzedTaskV2(BaseModel):
    task_id: str = Field(..., description="Unique identifier")
    task: str = Field(..., description="Brief task description")
    messages: List[str] = Field(..., description="User messages")
    workflow_trajectory: str = Field(..., description="Chronological workflow analysis")
    user_workflow_style: str = Field(..., description="How user thinks about tasks")
    problem: str = Field(default="", description="What AI did wrong in this task, or empty if no issue")
    ideal_trajectory: str = Field(..., description="How AI should guide user")
    rules: List[RuleV2] = Field(default_factory=list, description="Task-specific rules")
    
    model_config = ConfigDict(extra="forbid")


class TaskTypeV2(BaseModel):
    task_type_id: str = Field(..., description="Unique identifier")
    task_type: str = Field(..., description="Short task type name")
    reasoning: str = Field(..., description="Evidence for this categorization")
    user_mindset: str = Field(..., description="User's mental state in this mode")
    ai_guidance: str = Field(..., description="How AI should adapt")
    ai_donots: str = Field(..., description="What AI should avoid")
    common_problems: List[str] = Field(default_factory=list, description="Recurring AI mistakes in this task type")
    source_task_ids: List[str] = Field(default_factory=list, description="Tasks in this type")
    rules: List[RuleV2] = Field(default_factory=list, description="Rules for this task type")
    
    model_config = ConfigDict(extra="forbid")


class AnalyzedTasksV2DB(BaseModel):
    analyzed_tasks: List[AnalyzedTaskV2] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class TaskTypesV2DB(BaseModel):
    task_types: List[TaskTypeV2] = Field(default_factory=list)
    
    model_config = ConfigDict(extra="forbid")


class LearningV2DB(BaseModel):
    task_types: List[TaskTypeV2] = Field(default_factory=list)
    
    model_config = ConfigDict(extra="forbid")


# V3 Learning System Schemas

class AnalyzedTaskV3(BaseModel):
    task_id: str = Field(..., description="Unique identifier")
    task: str = Field(..., description="Brief task description")
    messages: List[str] = Field(..., description="User messages")
    description: str = Field(..., description="Chronological workflow evolution")
    type: Literal["good", "bad"] = Field(..., description="Trajectory quality")
    reasoning: str = Field(..., description="Why good or bad")
    problem: str = Field(default="", description="Root cause if bad, empty if good")
    failure_point: str = Field(default="", description="When/where it went wrong, empty if good")
    guardrail: str = Field(default="", description="How to recover, empty if good")
    rules: List[RuleV2] = Field(default_factory=list, description="Task-specific rules")
    
    suggested_type: Optional[str] = Field(None, description="Categorized task type (e.g., planning, debugging)")
    task_type_id: Optional[str] = Field(None, description="Assigned task type")
    suggested_types: List[str] = Field(default_factory=list, description="LLM-suggested types")
    
    model_config = ConfigDict(extra="forbid")


class AnalyzedTasksV3DB(BaseModel):
    analyzed_tasks: List[AnalyzedTaskV3] = Field(default_factory=list)
    
    model_config = ConfigDict(extra="forbid")


class PlanStep(BaseModel):
    step_number: int = Field(..., description="Step number")
    task_type: str = Field(..., description="Type of task (e.g., checking-with-user, planning, implementation, code-style)")
    objective: str = Field(..., description="What to do")
    rules: List[RuleV2] = Field(default_factory=list, description="Relevant rules")
    failure_point_watch: str = Field(default="", description="What to watch out for")
    substeps: List[str] = Field(default_factory=list, description="Sub-steps for incremental implementation")
    before_starting: Optional[str] = Field(None, description="Instructions for before starting this step")
    after_completing: Optional[str] = Field(None, description="Instructions for after completing this step")
    
    model_config = ConfigDict(extra="forbid")


class Plan(BaseModel):
    task_query: str = Field(..., description="Original query")
    good_trajectories: List[str] = Field(default_factory=list, description="Good past tasks")
    bad_trajectories: List[str] = Field(default_factory=list, description="Bad past tasks")
    reasoning: str = Field(..., description="Overall pattern analysis")
    steps: List[PlanStep] = Field(default_factory=list, description="Execution steps")
    
    model_config = ConfigDict(extra="forbid")
    
    model_config = ConfigDict(extra="forbid")


class TaskType(BaseModel):
    type_id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Short name (e.g., Planning, Debugging)")
    description: str = Field(..., description="What characterizes this type")
    color: str = Field(..., description="Hex color for UI")
    icon: str = Field(..., description="Material UI icon name")
    is_custom: bool = Field(default=False, description="User-created vs system")
    created_at: str = Field(..., description="ISO timestamp")
    
    model_config = ConfigDict(extra="forbid")


class TaskTypesDB(BaseModel):
    task_types: List[TaskType] = Field(default_factory=list)
    
    model_config = ConfigDict(extra="forbid")


class FavoritesDB(BaseModel):
    favorites: List[RuleV2] = Field(default_factory=list, description="List of favorite rules")
    
    model_config = ConfigDict(extra="forbid")


def get_schema(json_schema: dict) -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "json_output",
            "schema": json_schema,
        },
    }


class ChatMetadata(BaseModel):
    chat_id: str = Field(..., description="Unique identifier for chat")
    title: str = Field(..., description="Chat title (from first task query)")
    created_at: str = Field(..., description="ISO timestamp")
    updated_at: str = Field(..., description="ISO timestamp")
    
    model_config = ConfigDict(extra="forbid")


class ChatsMetadataDB(BaseModel):
    chats: List[ChatMetadata] = Field(default_factory=list)
    
    model_config = ConfigDict(extra="forbid")


class RuleRef(BaseModel):
    rule_id: str = Field(..., description="Rule identifier")
    name: str = Field(..., description="Short rule name")
    description: str = Field(..., description="Rule text")
    source: str = Field(..., description="Where rule came from")
    
    model_config = ConfigDict(extra="forbid")


class AuditEntry(BaseModel):
    at: str = Field(..., description="ISO timestamp")
    who: str = Field(..., description="Actor (user, ai, system)")
    action: str = Field(..., description="Action performed")
    details: str = Field(default="", description="Additional context")
    
    model_config = ConfigDict(extra="forbid")


class Node(BaseModel):
    id: str = Field(..., description="Unique node identifier")
    type: Literal["checking-with-user", "planning", "code-style", "debugging", "testing"] = Field(
        ..., description="Node type"
    )
    title: str = Field(..., description="Node title")
    description: str = Field(..., description="Node description")
    status: Literal["pending", "in_progress", "completed", "blocked"] = Field(
        default="pending", description="Node status"
    )
    rules: List[RuleRef] = Field(default_factory=list, description="Full rule objects for this step")
    notes: List[str] = Field(default_factory=list, description="Context, Q&A, observations")
    substeps: Optional[List[dict]] = Field(None, description="For code-style nodes only")
    audit: List[AuditEntry] = Field(default_factory=list, description="Audit trail")
    before_starting: Optional[str] = Field(None, description="Instructions for before starting this step")
    after_completing: Optional[str] = Field(None, description="Instructions for after completing this step")
    output: Optional[str] = Field(None, description="Execution output/result - e.g., strategy from planning node")
    
    model_config = ConfigDict(extra="forbid")


class PlanEdge(BaseModel):
    id: str = Field(..., description="Unique edge identifier")
    from_node: str = Field(..., alias="from", description="Source node ID")
    to_node: str = Field(..., alias="to", description="Target node ID")
    type: Literal["sequence", "dependency"] = Field(default="sequence", description="Edge type")
    
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class HistoryEntry(BaseModel):
    at: str = Field(..., description="ISO timestamp")
    action: str = Field(..., description="Action performed")
    details: str = Field(default="", description="Additional context")
    
    model_config = ConfigDict(extra="forbid")


class PlanModel(BaseModel):
    created_at: str = Field(..., description="ISO timestamp")
    updated_at: str = Field(..., description="ISO timestamp")
    nodes: List[Node] = Field(default_factory=list, description="Plan nodes")
    edges: List[PlanEdge] = Field(default_factory=list, description="Node connections")
    history: List[HistoryEntry] = Field(default_factory=list, description="Change history")
    
    model_config = ConfigDict(extra="forbid")


class FileSummary(BaseModel):
    path: str = Field(..., description="File path")
    lines_changed: str = Field(..., description="Line ranges changed (e.g., '45-50, 120-135')")
    changes: str = Field(..., description="What changed in this file")
    impact: str = Field(..., description="Why it matters / purpose")
    substeps_fulfilled: List[str] = Field(default_factory=list, description="Substep IDs this file fulfills")
    
    model_config = ConfigDict(extra="forbid")


class CodeBlock(BaseModel):
    file: str = Field(..., description="File path")
    lines: str = Field(..., description="Line range (e.g., '125-130')")
    code: str = Field(..., description="The actual code snippet")
    annotation: str = Field(..., description="Explanation of what this code does")
    
    model_config = ConfigDict(extra="forbid")


class SubstepRuleUsed(BaseModel):
    rule_id: str = Field(..., description="Rule identifier")
    rule_text: str = Field(..., description="Full rule text")
    how_used: str = Field(..., description="How rule was applied in this substep")
    
    model_config = ConfigDict(extra="forbid")


class SubstepVerification(BaseModel):
    substep_id: str = Field(..., description="Substep identifier")
    description: str = Field(..., description="Substep description")
    files_changed: List[str] = Field(default_factory=list, description="Files modified")
    code_changes: str = Field(..., description="What code changed")
    rules_used: List[SubstepRuleUsed] = Field(default_factory=list, description="Rules applied in this substep")
    timestamp: str = Field(..., description="ISO timestamp")
    
    model_config = ConfigDict(extra="forbid")


class RuleAnalysis(BaseModel):
    rule_id: str = Field(..., description="Rule identifier")
    rule_text: str = Field(..., description="Full rule text")
    followed: bool = Field(..., description="Whether rule was followed")
    evidence: str = Field(..., description="Grounded evidence from chat/code")
    used_in_substeps: List[str] = Field(default_factory=list, description="Substep IDs where this rule was used")
    
    model_config = ConfigDict(extra="forbid")


class VerifyResult(BaseModel):
    verdict: Literal["done", "not_done", "partial", "unclear"] = Field(..., description="Verification verdict")
    overview: str = Field(..., description="Markdown-formatted summary of what was done")
    rules_analysis: List[RuleAnalysis] = Field(default_factory=list, description="Per-rule compliance analysis")
    files_summary: List[FileSummary] = Field(default_factory=list, description="Summary of files changed")
    code_blocks: List[CodeBlock] = Field(default_factory=list, description="Specific code changes")
    timestamp: str = Field(..., description="ISO timestamp")
    
    model_config = ConfigDict(extra="forbid")


class IndividualTestResult(BaseModel):
    name: str = Field(..., description="Test name")
    category: str = Field(..., description="Test category (e.g., rule, substep)")
    description: str = Field(..., description="What the test validates in easy to undersatnd terms")
    status: Literal["pass", "fail", "error"] = Field(..., description="Test result status")
    output: str = Field(default="", description="Test output/error message")
    rule_description: Optional[str] = Field(None, description="Associated rule description if applicable")
    feature_name: Optional[str] = None  # ← ADD THIS
    test_code: str = Field(default="", description="The actual test code")
    
    model_config = ConfigDict(extra="forbid")


class DoResult(BaseModel):
    task_sent: str = Field(..., description="Task message sent to Cline")
    cline_response: str = Field(..., description="Response from Cline")
    verification_result: Optional[VerifyResult] = Field(None, description="Verification result after execution")
    timestamp: str = Field(..., description="ISO timestamp")
    
    model_config = ConfigDict(extra="forbid")


class TestResult(BaseModel):
    test_file: str = Field(default="", description="Path to generated test file")
    results: List[IndividualTestResult] = Field(default_factory=list, description="Individual test results")
    error: Optional[str] = Field(None, description="Error message if test generation failed")
    timestamp: str = Field(..., description="ISO timestamp")
    
    model_config = ConfigDict(extra="forbid")


class EnforcementRecord(BaseModel):
    node_id: str = Field(..., description="Node this enforcement belongs to")
    target_kind: Literal["step", "substep", "rule"] = Field(..., description="What is being enforced")
    target_id: str = Field(..., description="ID of the target (node_id, substep_id, or rule_id)")
    verify: Optional[VerifyResult] = Field(None, description="Verification results")
    do: Optional[DoResult] = Field(None, description="Do action results")
    test: Optional[TestResult] = Field(None, description="Test action results")
    
    model_config = ConfigDict(extra="forbid")


class EnforcementDB(BaseModel):
    records: List[EnforcementRecord] = Field(default_factory=list, description="Enforcement records")
    
    model_config = ConfigDict(extra="forbid")


# Enforcement V2 Schemas (requirement-driven workflow)

class Requirement(BaseModel):
    id: str = Field(..., description="Unique requirement ID (e.g., req-1, req-2)")
    description: str = Field(..., description="What needs to be verified/tested")
    category: Literal["feature", "rule", "integration", "edge"] = Field(..., description="Requirement category")
    source: Literal["auto", "user"] = Field(..., description="Generated by LLM or added by user")
    
    model_config = ConfigDict(extra="forbid")


class RequirementVerification(BaseModel):
    requirement_id: str = Field(..., description="ID of requirement being verified")
    verdict: Literal["pass", "fail", "unclear"] = Field(..., description="Verification verdict")
    evidence: str = Field(..., description="Grounded evidence for this requirement")
    files_changed: List[FileSummary] = Field(default_factory=list, description="Files changed for this requirement")
    code_changed: List[CodeBlock] = Field(default_factory=list, description="Code changes for this requirement")
    
    model_config = ConfigDict(extra="forbid")


class RequirementTest(BaseModel):
    requirement_id: str = Field(..., description="ID of requirement being tested")
    test_name: str = Field(..., description="Name of the test")
    test_description: str = Field(..., description="Human-readable explanation of what the test validates")
    test_code: str = Field(..., description="The actual test code")
    status: Literal["pass", "fail", "error"] = Field(..., description="Test execution status")
    output: str = Field(default="", description="Test output/error message")
    
    model_config = ConfigDict(extra="forbid")


class StepVerification(BaseModel):
    verdict: Literal["done", "not_done", "partial"] = Field(..., description="Verification verdict")
    overview: str = Field(..., description="Markdown-formatted summary")
    rules_analysis: List[RuleAnalysis] = Field(default_factory=list, description="Per-rule analysis")
    files_summary: List[FileSummary] = Field(default_factory=list, description="Files changed (code-style only)")
    code_blocks: List[CodeBlock] = Field(default_factory=list, description="Code snippets (code-style only)")
    timestamp: str = Field(..., description="ISO timestamp")
    
    model_config = ConfigDict(extra="forbid")


class EnforcementRecordV2(BaseModel):
    chat_id: str = Field(..., description="Chat this enforcement belongs to")
    node_id: str = Field(..., description="Node this enforcement belongs to")
    target_kind: Literal["substep", "step"] = Field(..., description="What is being enforced")
    target_id: str = Field(..., description="ID of the target (e.g., substep-1 or step-3)")
    requirements: List[Requirement] = Field(default_factory=list, description="List of requirements")
    verifications: List[RequirementVerification] = Field(default_factory=list, description="Per-requirement verifications")
    tests: List[RequirementTest] = Field(default_factory=list, description="Per-requirement tests")
    overall_verdict: Literal["done", "partial", "not_done"] = Field(default="not_done", description="Overall verdict")
    summary_text: str = Field(default="", description="Overall text summary of verification")
    files_changed: List[FileSummary] = Field(default_factory=list, description="Files that were changed")
    code_blocks: List[CodeBlock] = Field(default_factory=list, description="Specific code changes")
    step_verification: Optional[StepVerification] = Field(None, description="Step-level verification (when target_kind=step)")
    timestamp: str = Field(..., description="ISO timestamp")
    
    model_config = ConfigDict(extra="forbid")


class EnforcementV2DB(BaseModel):
    version: str = Field(default="2.0", description="Schema version")
    records: List[EnforcementRecordV2] = Field(default_factory=list, description="V2 enforcement records")
    
    model_config = ConfigDict(extra="forbid")


# V4 Learning System Schemas (Rules Only)
class AnalyzedTaskV4(BaseModel):
    task_id: str = Field(..., description="Unique identifier")
    description: str = Field(..., description="Chronological workflow evolution")
    rules: List[RuleV2] = Field(default_factory=list, description="Task-specific rules")
    
    model_config = ConfigDict(extra="forbid")

class AnalyzedTasksV4DB(BaseModel):
    analyzed_tasks: List[AnalyzedTaskV4] = Field(default_factory=list)
    
    model_config = ConfigDict(extra="forbid")
