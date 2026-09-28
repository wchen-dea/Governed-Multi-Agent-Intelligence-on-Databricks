"""Approval and delegation HTTP routes."""

from fastapi import APIRouter, HTTPException, Request

from aiserver.api.models import ApprovalDecisionInput
from aiserver.application.approvals.service import (
    ApprovalService,
    approval_payload,
    delegation_status_payload,
)
from aiserver.contracts.responses import ApprovalDecisionRequest

router = APIRouter()


def _service(request: Request) -> ApprovalService:
    return request.app.state.approval_service


async def submit(payload: ApprovalDecisionInput, request: Request) -> dict[str, object]:
    decision = ApprovalDecisionRequest(**payload.model_dump())
    try:
        return await _service(request).submit(decision)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/approval-decisions")
@router.post("/api/approvals")
@router.post("/api/v1/approvals")
async def submit_approval_decision(
    payload: ApprovalDecisionInput, request: Request
) -> dict[str, object]:
    return await submit(payload, request)


@router.get("/approval-decisions/{request_id}")
@router.get("/api/v1/approvals/{request_id}")
async def get_approval_decision(request_id: str, request: Request) -> dict[str, object]:
    record = _service(request).get(request_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval decision not found")
    return {"status": "ok", "approval": approval_payload(record)}


@router.get("/delegations/{task_id}")
@router.get("/api/v1/delegations/{task_id}")
async def get_delegation_status(task_id: str, request: Request) -> dict[str, object]:
    record = await request.app.state.container.delegation_task_bus.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Delegation task not found")
    return delegation_status_payload(record)
