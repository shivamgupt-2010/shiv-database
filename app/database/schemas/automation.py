from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# Action Definition Schemas
class ActionDefinitionBase(BaseModel):
    name: str
    category: str
    description: str
    risk_level: str = "SAFE"
    parameters_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = 60
    is_idempotent: bool = True
    is_enabled: bool = True


class ActionDefinitionCreate(ActionDefinitionBase):
    pass


class ActionDefinitionResponse(ActionDefinitionBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Plan Task Schemas
class PlanTaskRequest(BaseModel):
    intent: str
    constraints: Optional[Dict[str, Any]] = Field(default_factory=dict)
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    device_id: Optional[str] = None


class PlannedStep(BaseModel):
    id: str
    action: str
    title: str
    risk_level: str = "SAFE"
    requires_approval: bool = False
    depends_on: List[str] = Field(default_factory=list)
    inputs: Dict[str, Any] = Field(default_factory=dict)


class PlanTaskResponse(BaseModel):
    success: bool = True
    intent: str
    can_execute: bool
    summary: str
    unsupported_reasons: List[str] = Field(default_factory=list)
    steps: List[PlannedStep] = Field(default_factory=list)


# Task Run & Execution Schemas
class CreateTaskRequest(BaseModel):
    title: str
    workflow_id: Optional[str] = None
    trigger_source: str = "manual"
    steps: List[PlannedStep] = Field(default_factory=list)
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    auto_approve_safe: bool = True


class TaskStepResponse(BaseModel):
    id: str
    step_index: int
    step_identifier: str
    action_name: str
    depends_on: List[str] = Field(default_factory=list)
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Optional[Dict[str, Any]] = None
    status: str
    retry_count: int = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class TaskResponse(BaseModel):
    id: str
    workflow_id: Optional[str] = None
    user_id: str
    title: str
    trigger_source: str
    status: str
    context: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    steps: List[TaskStepResponse] = Field(default_factory=list)
    pending_approvals: List[Dict[str, Any]] = Field(default_factory=list)


# Approval Schemas
class ApproveTaskActionRequest(BaseModel):
    step_id: str
    decision: str = "APPROVED" # APPROVED, REJECTED
    reason: Optional[str] = None


class ApproveTaskActionResponse(BaseModel):
    success: bool
    task_id: str
    step_id: str
    decision: str
    message: str


# Workflow Schemas
class WorkflowStepDefinition(BaseModel):
    id: str
    action: str
    depends_on: List[str] = Field(default_factory=list)
    inputs: Dict[str, Any] = Field(default_factory=dict)


class CreateWorkflowRequest(BaseModel):
    name: str
    description: Optional[str] = None
    version: int = 1
    trigger: Dict[str, Any] = Field(default_factory=lambda: {"type": "manual"})
    steps: List[WorkflowStepDefinition]


class WorkflowResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: Optional[str] = None
    version: int
    trigger: Dict[str, Any]
    steps: List[WorkflowStepDefinition]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AutomationEventResponse(BaseModel):
    id: str
    task_run_id: str
    step_id: Optional[str] = None
    event_type: str
    message: str
    data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
