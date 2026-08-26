"""Approval-first spreadsheet AI proposals backed by an Ollama-compatible API."""
from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from typing import Any, Callable
from urllib import error, request

from sqlmodel import Session

from ..models import AIProposal
from .calculation import CalculationService
from .sheets import SheetRepository, SheetService


class AIServiceError(RuntimeError):
    pass


class OllamaProposalGenerator:
    def __init__(self) -> None:
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://192.168.1.249:11434").rstrip("/")
        self.model = os.getenv("OLLAMA_MODEL", "qwen3:14b")
        self.timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "90"))

    def __call__(self, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        system = (
            "You are a spreadsheet assistant. Return JSON only with summary, explanation, and operations. "
            "Allowed operation: {type:'set_cells',cells:[{row:int,col:int,value:string}]}. "
            "Use zero-based row and column indexes. Never claim changes were applied."
        )
        payload = json.dumps({"model": self.model, "stream": False, "format": "json", "prompt": f"{system}\nWorkbook context:\n{json.dumps(context)}\nUser request:\n{prompt}"}).encode()
        call = request.Request(f"{self.base_url}/api/generate", data=payload, headers={"Content-Type": "application/json"})
        try:
            with request.urlopen(call, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
            return json.loads(result.get("response", "{}"))
        except (error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            raise AIServiceError(f"AI model is unavailable or returned an invalid proposal: {exc}") from exc


class AIProposalService:
    def __init__(self, session: Session, generator: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None) -> None:
        self.session = session
        self.generator = generator or OllamaProposalGenerator()

    def propose(self, sheet_id: int, prompt: str, selection: dict[str, Any] | None = None) -> AIProposal:
        service = SheetService(SheetRepository(self.session))
        _, sheet_name, rows, cols, data = service.fetch_sheet(sheet_id)
        context = {"sheetId": sheet_id, "sheetName": sheet_name, "dimensions": {"rows": rows, "columns": cols}, "selection": selection or {}, "sample": [row[:20] for row in data[:50]]}
        raw = self.generator(prompt, context)
        operations = _validate_operations(raw.get("operations", []), rows, cols)
        proposal = AIProposal(sheet_id=sheet_id, user_prompt=prompt, summary=str(raw.get("summary") or "Spreadsheet changes"), explanation=str(raw.get("explanation") or ""), operations_json=json.dumps(operations, separators=(",", ":")))
        self.session.add(proposal); self.session.commit(); self.session.refresh(proposal)
        return proposal

    def decide(self, proposal_id: str, approve: bool) -> AIProposal:
        proposal = self.session.get(AIProposal, proposal_id)
        if proposal is None: raise LookupError("Proposal not found")
        if proposal.status != "pending": raise AIServiceError("Proposal has already been decided")
        if approve:
            repository = SheetRepository(self.session); service = SheetService(repository)
            for operation in json.loads(proposal.operations_json):
                if operation["type"] == "set_cells": service.apply_updates(proposal.sheet_id, operation["cells"], validate=True)
            CalculationService(self.session).recalculate_sheet(proposal.sheet_id)
            proposal.status = "approved"
        else:
            proposal.status = "rejected"
        proposal.decided_at = datetime.now(UTC); self.session.add(proposal); self.session.commit(); self.session.refresh(proposal)
        return proposal


def serialize_proposal(proposal: AIProposal) -> dict[str, Any]:
    return {"id": proposal.id, "sheetId": proposal.sheet_id, "prompt": proposal.user_prompt, "summary": proposal.summary, "explanation": proposal.explanation, "operations": json.loads(proposal.operations_json), "status": proposal.status, "createdAt": proposal.created_at.isoformat()}


def _validate_operations(raw: Any, rows: int, cols: int) -> list[dict[str, Any]]:
    if not isinstance(raw, list): raise AIServiceError("AI operations must be a list")
    validated = []; total = 0
    for operation in raw:
        if not isinstance(operation, dict) or operation.get("type") != "set_cells": raise AIServiceError("AI proposed an unsupported operation")
        cells = []
        for cell in operation.get("cells", []):
            if not isinstance(cell, dict): continue
            row, col = cell.get("row"), cell.get("col")
            if not isinstance(row, int) or not isinstance(col, int) or row < 0 or col < 0 or row >= rows or col >= cols: raise AIServiceError("AI proposal contains an out-of-range cell")
            cells.append({"row": row, "col": col, "value": "" if cell.get("value") is None else str(cell.get("value"))}); total += 1
            if total > 1000: raise AIServiceError("AI proposal exceeds the 1,000-cell safety limit")
        validated.append({"type": "set_cells", "cells": cells})
    return validated
