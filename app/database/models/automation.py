from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.models.base import Base


class ActionDefinition(Base):
    """Catalog of registered, schema-validated actions available in SHIV ecosystem."""
    __tablename__ = "action_definitions"

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(50), index=True, nullable=False) # android, web, media, system, desktop
    description: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(30), default="SAFE", nullable=False) # SAFE, CONFIRMATION_REQUIRED, CRITICAL
    parameters_schema_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    output_schema_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    is_idempotent: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AutomationWorkflow(Base):
    """Versioned automation workflows composed of structured DAG steps."""
    __tablename__ = "automation_workflows"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    trigger_config_json: Mapped[str] = mapped_column(Text, default="{\"type\": \"manual\"}", nullable=False)
    steps_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AutomationTrigger(Base):
    """Triggers and schedules for automated workflow execution."""
    __tablename__ = "automation_triggers"

    workflow_id: Mapped[str] = mapped_column(String(36), ForeignKey("automation_workflows.id", ondelete="CASCADE"), index=True, nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False) # manual, schedule, event, webhook
    cron_expression: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    event_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    config_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class TaskRun(Base):
    """Active or historical task execution lifecycle record."""
    __tablename__ = "task_runs"

    workflow_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("automation_workflows.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    trigger_source: Mapped[str] = mapped_column(String(50), default="manual", nullable=False) # manual, voice_assistant, schedule, event
    status: Mapped[str] = mapped_column(String(50), default="QUEUED", index=True, nullable=False) # QUEUED, PLANNING, AWAITING_APPROVAL, RUNNING, PAUSED, COMPLETED, FAILED, CANCELLED
    plan_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    context_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    steps: Mapped[list["TaskStep"]] = relationship("TaskStep", back_populates="task_run", cascade="all, delete-orphan")


class TaskStep(Base):
    """Individual execution step within a task DAG."""
    __tablename__ = "task_steps"

    task_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("task_runs.id", ondelete="CASCADE"), index=True, nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_identifier: Mapped[str] = mapped_column(String(100), nullable=False)
    action_name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    depends_on_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    inputs_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    outputs_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", index=True, nullable=False) # PENDING, AWAITING_APPROVAL, RUNNING, COMPLETED, FAILED, SKIPPED
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    task_run: Mapped["TaskRun"] = relationship("TaskRun", back_populates="steps")


class ActionApproval(Base):
    """Explicit confirmation requests for sensitive or high-risk actions."""
    __tablename__ = "action_approvals"

    task_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("task_runs.id", ondelete="CASCADE"), index=True, nullable=False)
    step_id: Mapped[str] = mapped_column(String(36), ForeignKey("task_steps.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    action_name: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(30), default="CONFIRMATION_REQUIRED", nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    decision: Mapped[str] = mapped_column(String(30), default="PENDING", index=True, nullable=False) # PENDING, APPROVED, REJECTED, EXPIRED
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ConnectedDevice(Base):
    """Authenticated launcher and desktop agents linked to a user account."""
    __tablename__ = "connected_devices"

    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    device_name: Mapped[str] = mapped_column(String(150), nullable=False)
    device_type: Mapped[str] = mapped_column(String(50), nullable=False) # ANDROID_LAUNCHER, DESKTOP_WINDOWS, DESKTOP_MACOS, WEB
    device_fingerprint: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    permissions_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AutomationEvent(Base):
    """Real-time event and progress updates emitted during task execution."""
    __tablename__ = "automation_events"

    task_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("task_runs.id", ondelete="CASCADE"), index=True, nullable=False)
    step_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False) # INFO, STEP_START, STEP_DONE, APPROVAL_REQ, ERROR
    message: Mapped[str] = mapped_column(Text, nullable=False)
    data_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)


class ActionAuditLog(Base):
    """Immutable audit trail of all initiated, authorized, and executed actions."""
    __tablename__ = "action_audit_logs"

    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    device_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    task_run_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    action_name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    target_resource: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    risk_level: Mapped[str] = mapped_column(String(30), nullable=False)
    approval_status: Mapped[str] = mapped_column(String(50), default="AUTO", nullable=False) # AUTO, EXPLICIT_USER, SYSTEM
    outcome: Mapped[str] = mapped_column(String(50), nullable=False) # SUCCESS, FAILED, BLOCKED
    details_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
