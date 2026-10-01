from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.eigi import EigiService
from app.attempts import InterviewAttempt, attempt_store
from app.schemas import (
    ClientConfig,
    CompleteInterviewRequest,
    InterviewAnalysis,
    InterviewAttemptResponse,
    ResumeResponse,
    StartInterviewRequest,
    StartInterviewResponse,
)
from app.resumes import extract_resume
from app.settings import Settings, get_settings

app = FastAPI(title="LRN Voice Interview API")
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config", response_model=ClientConfig)
async def config(current: Settings = Depends(get_settings)) -> ClientConfig:
    return ClientConfig(configured=current.eigi_configured)


@app.post("/api/resume", response_model=ResumeResponse)
async def upload_resume(file: UploadFile) -> ResumeResponse:
    filename, resume_context = await extract_resume(file)
    return ResumeResponse(filename=filename, resume_context=resume_context)


@app.post("/api/interviews", response_model=StartInterviewResponse)
async def start_interview(
    payload: StartInterviewRequest,
    current: Settings = Depends(get_settings),
) -> StartInterviewResponse:
    attempt = attempt_store.create(payload)
    try:
        result = await EigiService(current).create_session(payload, attempt.attempt_id)
    except Exception:
        attempt_store.remove(attempt.attempt_id)
        raise
    attempt_store.attach_conversation(attempt.attempt_id, result["conversation_id"])
    return StartInterviewResponse(attempt_id=attempt.attempt_id, **result)


def serialize_attempt(attempt: InterviewAttempt) -> InterviewAttemptResponse:
    return InterviewAttemptResponse(
        attempt_id=attempt.attempt_id,
        conversation_id=attempt.conversation_id,
        status=attempt.status,
        brief=attempt.brief,
        transcript=attempt.transcript,
        report=attempt.report,
    )


async def refresh_analysis(attempt: InterviewAttempt, current: Settings) -> InterviewAttempt:
    if (
        not attempt.conversation_id
        or not current.eigi_configured
        or (attempt.report is not None and attempt.report.status == "ready")
    ):
        return attempt
    try:
        conversation = await EigiService(current).get_conversation(attempt.conversation_id)
        provider_analysis = conversation.get("conversation_analysis")
        if isinstance(provider_analysis, list) and provider_analysis:
            provider_analysis = provider_analysis[0]
        if isinstance(provider_analysis, dict) and provider_analysis:
            return attempt_store.attach_analysis(attempt.attempt_id, InterviewAnalysis.model_validate(provider_analysis))
    except (HTTPException, ValueError):
        # Analysis is asynchronous; the report endpoint will retry without losing the transcript.
        pass
    return attempt


@app.post("/api/interviews/{attempt_id}/complete", response_model=InterviewAttemptResponse)
async def complete_interview(
    attempt_id: str,
    payload: CompleteInterviewRequest,
    current: Settings = Depends(get_settings),
) -> InterviewAttemptResponse:
    attempt = attempt_store.get(attempt_id)
    attempt_store.complete(attempt_id, payload.transcript)
    return serialize_attempt(await refresh_analysis(attempt, current))


@app.get("/api/interviews/{attempt_id}", response_model=InterviewAttemptResponse)
async def get_interview(
    attempt_id: str,
    current: Settings = Depends(get_settings),
) -> InterviewAttemptResponse:
    return serialize_attempt(await refresh_analysis(attempt_store.get(attempt_id), current))
