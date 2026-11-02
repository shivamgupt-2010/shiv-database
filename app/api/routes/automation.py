import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc

from app.database.session import get_db_session as get_db
from app.api.dependencies import get_current_user, get_auth_service
from app.database.models.auth import User
from app.database.models.automation import (
    ActionDefinition,
    AutomationWorkflow,
    AutomationTrigger,
    TaskRun,
    TaskStep,
    ActionApproval,
    ConnectedDevice,
    AutomationEvent,
    ActionAuditLog,
)
from app.database.schemas.automation import (
    ActionDefinitionCreate,
    ActionDefinitionResponse,
    PlanTaskRequest,
    PlanTaskResponse,
    PlannedStep,
    CreateTaskRequest,
    TaskResponse,
    TaskStepResponse,
    ApproveTaskActionRequest,
    ApproveTaskActionResponse,
    CreateWorkflowRequest,
    WorkflowResponse,
    AutomationEventResponse,
)

router = APIRouter(prefix="/v1", tags=["Action & Automation Engine"])

def utc_now():
    return datetime.now(timezone.utc)


# ============================================================================
# 1. ACTION REGISTRY ENDPOINTS
# ============================================================================

@router.get("/actions", response_model=Dict[str, Any])
async def list_actions(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List all actions available in the SHIV Action Registry."""
    query = select(ActionDefinition).where(ActionDefinition.is_enabled == True)
    if category:
        query = query.where(ActionDefinition.category == category)
    
    result = await db.execute(query)
    actions = result.scalars().all()

    action_list = []
    for a in actions:
        try:
            params = json.loads(a.parameters_schema_json)
        except Exception:
            params = {}
        try:
            output = json.loads(a.output_schema_json)
        except Exception:
            output = {}

        action_list.append({
            "id": a.id,
            "name": a.name,
            "category": a.category,
            "description": a.description,
            "risk_level": a.risk_level,
            "parameters_schema": params,
            "output_schema": output,
            "timeout_seconds": a.timeout_seconds,
            "is_idempotent": a.is_idempotent,
            "is_enabled": a.is_enabled,
        })

    return {
        "success": True,
        "count": len(action_list),
        "actions": action_list
    }


# ============================================================================
# 2. TASK PLANNING & CAPABILITY INSPECTION
# ============================================================================

@router.post("/tasks/plan", response_model=PlanTaskResponse)
async def plan_task(
    req: PlanTaskRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Decomposes natural language intent into an ordered execution DAG.
    Checks capability registry, required approvals, and flags unsupported requests honestly.
    """
    intent_lower = req.intent.lower().strip()
    steps: List[PlannedStep] = []
    unsupported_reasons: List[str] = []

    # Fetch available action definitions
    result = await db.execute(select(ActionDefinition).where(ActionDefinition.is_enabled == True))
    all_actions = {a.name: a for a in result.scalars().all()}

    # Intelligent intent decomposition patterns
    if "video" in intent_lower and ("create" in intent_lower or "generate" in intent_lower or "prepare" in intent_lower or "edit" in intent_lower):
        # Multi-step video pipeline
        steps.append(PlannedStep(
            id="gather_assets",
            action="files.list",
            title="Inspect project media and assets",
            risk_level="SAFE",
            requires_approval=False,
            inputs={"folder": "media/assets"}
        ))
        steps.append(PlannedStep(
            id="generate_video",
            action="media.video.generate",
            title="Generate 30-second promotional video sequence",
            risk_level="CONFIRMATION_REQUIRED",
            requires_approval=True,
            depends_on=["gather_assets"],
            inputs={"prompt": req.intent, "durationSec": 30, "aspect_ratio": "16:9"}
        ))
        steps.append(PlannedStep(
            id="organize_export",
            action="files.organize",
            title="Organize final render to output destination",
            risk_level="SAFE",
            requires_approval=False,
            depends_on=["generate_video"],
            inputs={"destination": "output/videos"}
        ))
        steps.append(PlannedStep(
            id="verify_output",
            action="files.verify",
            title="Verify exported video file integrity and duration",
            risk_level="SAFE",
            requires_approval=False,
            depends_on=["organize_export"],
            inputs={"expected_min_bytes": 102400}
        ))

    elif "website" in intent_lower or "webpage" in intent_lower or "landing page" in intent_lower:
        steps.append(PlannedStep(
            id="generate_code",
            action="media.website.create",
            title="Generate responsive web application bundle",
            risk_level="SAFE",
            requires_approval=False,
            inputs={"prompt": req.intent, "filename": "index.html"}
        ))
        steps.append(PlannedStep(
            id="preview_browser",
            action="android.app.open",
            title="Launch website preview in default browser",
            risk_level="SAFE",
            requires_approval=False,
            depends_on=["generate_code"],
            inputs={"package_name": "com.android.chrome"}
        ))

    elif "open" in intent_lower or "launch" in intent_lower:
        # App launch intent
        app_name = intent_lower.replace("open", "").replace("launch", "").replace("my", "").replace("app", "").strip()
        steps.append(PlannedStep(
            id="launch_app",
            action="android.app.open",
            title=f"Launch application: {app_name}",
            risk_level="SAFE",
            requires_approval=False,
            inputs={"query": app_name}
        ))

    elif "organize" in intent_lower and "file" in intent_lower:
        steps.append(PlannedStep(
            id="find_files",
            action="files.list",
            title="List files in target project folder",
            risk_level="SAFE",
            requires_approval=False,
            inputs={"folder": "downloads"}
        ))
        steps.append(PlannedStep(
            id="organize_files",
            action="files.organize",
            title="Categorize and move files to organized folders",
            risk_level="SAFE",
            requires_approval=False,
            depends_on=["find_files"],
            inputs={"destination": "documents/organized"}
        ))
        steps.append(PlannedStep(
            id="verify",
            action="files.verify",
            title="Verify file organization outcome",
            risk_level="SAFE",
            requires_approval=False,
            depends_on=["organize_files"],
            inputs={}
        ))

    elif "search" in intent_lower or "research" in intent_lower:
        query = intent_lower.replace("search", "").replace("research", "").replace("for", "").strip()
        steps.append(PlannedStep(
            id="web_search",
            action="web.search",
            title=f"Perform neural web search: {query}",
            risk_level="SAFE",
            requires_approval=False,
            inputs={"query": query}
        ))

    else:
        # General intelligent task
        steps.append(PlannedStep(
            id="execute_goal",
            action="ai.reasoning",
            title="Analyze and execute request through cognitive core",
            risk_level="SAFE",
            requires_approval=False,
            inputs={"prompt": req.intent}
        ))

    # Validate steps against action registry
    can_execute = True
    for s in steps:
        if s.action not in all_actions:
            # Check if dynamically synthesized
            if not s.action.startswith("ai."):
                can_execute = False
                unsupported_reasons.append(f"Action '{s.action}' is not registered or supported by available adapters.")

    summary = f"Planned {len(steps)} steps for intent: '{req.intent}'."
    if not can_execute:
        summary += " Note: Some steps require external software or unsupported adapters."

    return PlanTaskResponse(
        success=True,
        intent=req.intent,
        can_execute=can_execute,
        summary=summary,
        unsupported_reasons=unsupported_reasons,
        steps=steps
    )


# ============================================================================
# 3. TASK LIFECYCLE (CREATE, EXECUTE, STATUS, APPROVE, CANCEL, EVENTS)
# ============================================================================

@router.post("/tasks", response_model=Dict[str, Any])
async def create_task(
    req: CreateTaskRequest,
    db: AsyncSession = Depends(get_db)
):
    """Creates a task run from an authorized execution plan and initializes steps."""
    # Default to system admin/guest user if unauthenticated
    user_result = await db.execute(select(User).limit(1))
    default_user = user_result.scalars().first()
    user_id = default_user.id if default_user else "usr_system_default"

    task_id = f"task_{uuid.uuid4().hex[:12]}"
    task_run = TaskRun(
        id=task_id,
        workflow_id=req.workflow_id,
        user_id=user_id,
        title=req.title,
        trigger_source=req.trigger_source,
        status="PLANNING",
        plan_json=json.dumps({"steps": [s.model_dump() for s in req.steps]}),
        context_json=json.dumps(req.context or {}),
        started_at=utc_now()
    )
    db.add(task_run)
    await db.flush()

    # Create step entities & check approvals
    has_approval_blocker = False
    first_step_id = None

    for idx, s in enumerate(req.steps):
        step_id = f"step_{uuid.uuid4().hex[:12]}"
        if idx == 0:
            first_step_id = step_id

        step_status = "PENDING"
        if s.requires_approval or s.risk_level in ["CONFIRMATION_REQUIRED", "CRITICAL"]:
            step_status = "AWAITING_APPROVAL"
            has_approval_blocker = True
            
            # Create ActionApproval record
            approval = ActionApproval(
                id=f"appr_{uuid.uuid4().hex[:12]}",
                task_run_id=task_id,
                step_id=step_id,
                user_id=user_id,
                action_name=s.action,
                summary=f"Approval requested for step '{s.title}' ({s.action})",
                risk_level=s.risk_level,
                payload_json=json.dumps(s.inputs),
                decision="PENDING"
            )
            db.add(approval)

        step_entity = TaskStep(
            id=step_id,
            task_run_id=task_id,
            step_index=idx,
            step_identifier=s.id,
            action_name=s.action,
            depends_on_json=json.dumps(s.depends_on),
            inputs_json=json.dumps(s.inputs),
            status=step_status
        )
        db.add(step_entity)

    # Add initial event
    event = AutomationEvent(
        id=f"evt_{uuid.uuid4().hex[:12]}",
        task_run_id=task_id,
        event_type="INFO",
        message=f"Task '{req.title}' created with {len(req.steps)} steps.",
        data_json=json.dumps({"trigger_source": req.trigger_source})
    )
    db.add(event)

    task_run.status = "AWAITING_APPROVAL" if has_approval_blocker else "RUNNING"
    await db.commit()

    return {
        "success": True,
        "task_id": task_id,
        "status": task_run.status,
        "title": req.title,
        "steps_count": len(req.steps),
        "requires_approval": has_approval_blocker,
        "message": "Task queued for execution." if not has_approval_blocker else "Task paused awaiting user confirmation."
    }


@router.get("/tasks/{task_id}", response_model=Dict[str, Any])
async def get_task_status(
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieve full status, step outputs, and pending approvals for a task."""
    result = await db.execute(select(TaskRun).where(TaskRun.id == task_id))
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Fetch steps
    steps_res = await db.execute(select(TaskStep).where(TaskStep.task_run_id == task_id).order_by(TaskStep.step_index))
    steps = steps_res.scalars().all()

    # Fetch pending approvals
    appr_res = await db.execute(select(ActionApproval).where(ActionApproval.task_run_id == task_id, ActionApproval.decision == "PENDING"))
    approvals = appr_res.scalars().all()

    step_data = []
    for s in steps:
        step_data.append({
            "id": s.id,
            "step_index": s.step_index,
            "step_identifier": s.step_identifier,
            "action_name": s.action_name,
            "depends_on": json.loads(s.depends_on_json),
            "inputs": json.loads(s.inputs_json),
            "outputs": json.loads(s.outputs_json) if s.outputs_json else None,
            "status": s.status,
            "retry_count": s.retry_count,
            "error_message": s.error_message,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None
        })

    approval_data = [{
        "id": a.id,
        "step_id": a.step_id,
        "action_name": a.action_name,
        "summary": a.summary,
        "risk_level": a.risk_level,
        "payload": json.loads(a.payload_json),
        "decision": a.decision
    } for a in approvals]

    return {
        "success": True,
        "id": task.id,
        "workflow_id": task.workflow_id,
        "title": task.title,
        "trigger_source": task.trigger_source,
        "status": task.status,
        "error_message": task.error_message,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "steps": step_data,
        "pending_approvals": approval_data
    }


@router.post("/tasks/{task_id}/approve", response_model=ApproveTaskActionResponse)
async def approve_task_action(
    task_id: str,
    req: ApproveTaskActionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Approves or rejects a sensitive action awaiting user confirmation."""
    appr_res = await db.execute(
        select(ActionApproval).where(
            ActionApproval.task_run_id == task_id,
            ActionApproval.step_id == req.step_id,
            ActionApproval.decision == "PENDING"
        )
    )
    approval = appr_res.scalars().first()
    if not approval:
        raise HTTPException(status_code=404, detail="Pending approval not found for step")

    now = utc_now()
    approval.decision = req.decision.upper()
    approval.decided_at = now

    # Update corresponding step
    step_res = await db.execute(select(TaskStep).where(TaskStep.id == req.step_id))
    step = step_res.scalars().first()

    if step:
        if approval.decision == "APPROVED":
            step.status = "RUNNING"
            step.started_at = now
            # Log audit event
            audit_log = ActionAuditLog(
                user_id=approval.user_id,
                task_run_id=task_id,
                action_name=approval.action_name,
                target_resource=step.step_identifier,
                risk_level=approval.risk_level,
                approval_status="EXPLICIT_USER",
                outcome="SUCCESS",
                details_json=json.dumps({"approved_at": now.isoformat(), "reason": req.reason or "User approved via UI"})
            )
            db.add(audit_log)
        else:
            step.status = "FAILED"
            step.error_message = f"User rejected action: {req.reason or 'User denied permission'}"
            step.completed_at = now

    # Check if remaining approvals exist
    remaining_apprs = await db.execute(
        select(ActionApproval).where(
            ActionApproval.task_run_id == task_id,
            ActionApproval.decision == "PENDING"
        )
    )
    if not remaining_apprs.scalars().all():
        task_res = await db.execute(select(TaskRun).where(TaskRun.id == task_id))
        task = task_res.scalars().first()
        if task and task.status == "AWAITING_APPROVAL":
            task.status = "RUNNING"

    await db.commit()

    return ApproveTaskActionResponse(
        success=True,
        task_id=task_id,
        step_id=req.step_id,
        decision=approval.decision,
        message=f"Action '{approval.action_name}' {approval.decision.lower()} successfully."
    )


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Cancels a running or paused task."""
    result = await db.execute(select(TaskRun).where(TaskRun.id == task_id))
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = "CANCELLED"
    task.completed_at = utc_now()

    # Cancel pending steps
    await db.execute(
        update(TaskStep)
        .where(TaskStep.task_run_id == task_id, TaskStep.status.in_(["PENDING", "AWAITING_APPROVAL"]))
        .values(status="SKIPPED", error_message="Task cancelled by user")
    )

    event = AutomationEvent(
        task_run_id=task_id,
        event_type="INFO",
        message="Task execution cancelled by user request."
    )
    db.add(event)
    await db.commit()

    return {"success": True, "task_id": task_id, "status": "CANCELLED"}


@router.get("/tasks/{task_id}/events")
async def get_task_events(
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Streams execution progress, errors, and outcomes."""
    res = await db.execute(select(AutomationEvent).where(AutomationEvent.task_run_id == task_id).order_by(AutomationEvent.created_at.asc()))
    events = res.scalars().all()

    return {
        "success": True,
        "task_id": task_id,
        "events": [{
            "id": e.id,
            "step_id": e.step_id,
            "event_type": e.event_type,
            "message": e.message,
            "data": json.loads(e.data_json),
            "created_at": e.created_at.isoformat()
        } for e in events]
    }


# ============================================================================
# 4. WORKFLOW DEFINITIONS & RUNS
# ============================================================================

@router.post("/workflows", response_model=Dict[str, Any])
async def create_workflow(
    req: CreateWorkflowRequest,
    db: AsyncSession = Depends(get_db)
):
    """Persists a versioned workflow definition."""
    user_result = await db.execute(select(User).limit(1))
    default_user = user_result.scalars().first()
    user_id = default_user.id if default_user else "usr_system_default"

    wf_id = f"wf_{uuid.uuid4().hex[:12]}"
    workflow = AutomationWorkflow(
        id=wf_id,
        user_id=user_id,
        name=req.name,
        description=req.description,
        version=req.version,
        trigger_config_json=json.dumps(req.trigger),
        steps_json=json.dumps([s.model_dump() for s in req.steps]),
        is_active=True
    )
    db.add(workflow)
    await db.commit()

    return {
        "success": True,
        "workflow_id": wf_id,
        "name": req.name,
        "version": req.version,
        "steps_count": len(req.steps)
    }


@router.post("/workflows/{workflow_id}/runs", response_model=Dict[str, Any])
async def run_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Instantiates a task run from a saved workflow definition."""
    result = await db.execute(select(AutomationWorkflow).where(AutomationWorkflow.id == workflow_id))
    workflow = result.scalars().first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    steps_raw = json.loads(workflow.steps_json)
    planned_steps = [PlannedStep(
        id=s.get("id", f"step_{idx}"),
        action=s["action"],
        title=f"Execute {s['action']}",
        depends_on=s.get("depends_on", []),
        inputs=s.get("inputs", {})
    ) for idx, s in enumerate(steps_raw)]

    task_req = CreateTaskRequest(
        title=f"Run: {workflow.name}",
        workflow_id=workflow.id,
        trigger_source="manual",
        steps=planned_steps
    )
    return await create_task(task_req, db)
