from io import BytesIO

from docx import Document
from fastapi.testclient import TestClient

from app.eigi import EigiService
from app.attempts import attempt_store
from app.main import app
from app.schemas import StartInterviewRequest
from app.settings import Settings, get_settings


client = TestClient(app)


def test_health() -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_unconfigured_session_fails_without_exposing_secrets() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        eigi_base_url="",
        eigi_api_key="",
        eigi_agent_id="",
    )
    try:
        response = client.post(
            "/api/interviews",
            json={
                "target_role": "Investment banking",
                "focus_area": "Valuation",
                "interview_mode": "realistic",
                "duration_minutes": 15,
            },
        )
        assert response.status_code == 503
        assert response.json() == {"detail": "Voice interviews are not configured yet."}
    finally:
        app.dependency_overrides.clear()


def test_invalid_interview_is_rejected() -> None:
    response = client.post(
        "/api/interviews",
        json={
            "target_role": "",
            "focus_area": "Valuation",
            "interview_mode": "unsupported",
            "duration_minutes": 60,
        },
    )
    assert response.status_code == 422


def test_resume_upload_extracts_text_and_removes_contact_details() -> None:
    document = Document()
    document.add_paragraph(
        "Ada Lovelace · ada@example.com · +91 98765 43210\n"
        "Built a financial model and presented valuation recommendations to senior stakeholders."
    )
    content = BytesIO()
    document.save(content)

    response = client.post(
        "/api/resume",
        files={"file": ("ada-resume.docx", content.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert response.status_code == 200
    assert response.json()["filename"] == "ada-resume.docx"
    assert "[email removed]" in response.json()["resume_context"]
    assert "[phone removed]" in response.json()["resume_context"]
    assert "financial model" in response.json()["resume_context"]


def test_resume_upload_rejects_unsupported_files() -> None:
    response = client.post("/api/resume", files={"file": ("resume.txt", b"plain text", "text/plain")})
    assert response.status_code == 422


def test_completion_saves_transcript_and_is_retry_safe() -> None:
    attempt = attempt_store.create(
        StartInterviewRequest(
            target_role="Investment banking",
            focus_area="Valuation",
            interview_mode="realistic",
            duration_minutes=15,
        )
    )
    attempt_store.attach_conversation(attempt.attempt_id, "conversation-1")
    payload = {
        "transcript": [
            {"speaker": "interviewer", "text": "Walk me through"},
            {"speaker": "interviewer", "text": "a DCF."},
            {"speaker": "candidate", "text": "First, project free cash flow."},
        ]
    }

    first = client.post(f"/api/interviews/{attempt.attempt_id}/complete", json=payload)
    second = client.post(f"/api/interviews/{attempt.attempt_id}/complete", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "completed"
    assert second.json()["brief"]["focus_area"] == "Valuation"
    assert [item["text"] for item in second.json()["transcript"]] == [
        "Walk me through a DCF.",
        "First, project free cash flow.",
    ]
    assert second.json()["report"]["status"] == "pending_provider"


def test_unknown_interview_cannot_be_completed() -> None:
    response = client.post("/api/interviews/missing/complete", json={"transcript": []})
    assert response.status_code == 404


def test_pending_report_refreshes_when_provider_analysis_arrives(monkeypatch) -> None:
    attempt = attempt_store.create(
        StartInterviewRequest(
            target_role="Consulting",
            focus_area="Behavioural",
            interview_mode="realistic",
            duration_minutes=15,
        )
    )
    attempt_store.attach_conversation(attempt.attempt_id, "conversation-analysis")
    attempt_store.complete(attempt.attempt_id, [])
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        eigi_base_url="https://api.eigi.ai",
        eigi_api_key="test-key",
        eigi_agent_id="agent-id",
    )

    async def provider_analysis(*_args, **_kwargs):
        return {
            "conversation_analysis": [{
                "overall_score": 75,
                "communication_clarity_score": 76,
                "answer_structure_score": 72,
                "role_knowledge_score": 74,
                "analytical_reasoning_score": 78,
                "evidence_specificity_score": 70,
                "strengths": ["Clear structure"],
                "improvement_areas": ["Quantify impact"],
                "recommended_next_steps": ["Practise STAR answers"],
                "summary": "A solid interview with specific improvement opportunities.",
            }]
        }

    monkeypatch.setattr(EigiService, "get_conversation", provider_analysis)
    try:
        response = client.get(f"/api/interviews/{attempt.attempt_id}")
        assert response.status_code == 200
        assert response.json()["report"]["status"] == "ready"
        assert response.json()["report"]["analysis"]["overall_score"] == 75
    finally:
        app.dependency_overrides.clear()

