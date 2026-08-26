from app.models import AIProposal, SheetCell
from app.services.ai import AIProposalService, AIServiceError
from app.services.database import get_session


def test_ai_proposal_requires_approval_before_changes(app, client):
    sheet_id = client.get("/api/grid").get_json()["sheetId"]

    def generator(prompt, context):
        assert context["sheetId"] == sheet_id
        return {"summary": "Add total", "explanation": "Adds a safe formula", "operations": [{"type": "set_cells", "cells": [{"row": 0, "col": 1, "value": "=A1*2"}]}]}

    with app.app_context():
        service = AIProposalService(get_session(), generator)
        proposal = service.propose(sheet_id, "Add a total")
        assert proposal.status == "pending"
        assert get_session().get(SheetCell, (sheet_id, 0, 1)) is None
        service.decide(proposal.id, True)
        assert get_session().get(SheetCell, (sheet_id, 0, 1)).formula == "=A1*2"
        assert get_session().get(AIProposal, proposal.id).status == "approved"


def test_rejected_ai_proposal_does_not_change_sheet(app, client):
    sheet_id = client.get("/api/grid").get_json()["sheetId"]
    generator = lambda *_: {"summary": "Change", "operations": [{"type": "set_cells", "cells": [{"row": 1, "col": 1, "value": "No"}]}]}
    with app.app_context():
        service = AIProposalService(get_session(), generator)
        proposal = service.propose(sheet_id, "Change cell")
        service.decide(proposal.id, False)
        assert get_session().get(SheetCell, (sheet_id, 1, 1)) is None


def test_ai_proposal_rejects_out_of_range_changes(app, client):
    sheet_id = client.get("/api/grid").get_json()["sheetId"]
    generator = lambda *_: {"summary": "Unsafe", "operations": [{"type": "set_cells", "cells": [{"row": 999, "col": 0, "value": "x"}]}]}
    with app.app_context():
        try:
            AIProposalService(get_session(), generator).propose(sheet_id, "Unsafe")
            assert False, "Expected AIServiceError"
        except AIServiceError:
            pass
