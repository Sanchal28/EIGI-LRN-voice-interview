from typing import Literal

from pydantic import BaseModel, Field


class StartInterviewRequest(BaseModel):
    target_role: str = Field(min_length=1, max_length=100)
    focus_area: str = Field(min_length=1, max_length=100)
    interview_mode: Literal["realistic", "guided"]
    duration_minutes: Literal[15, 30]
    resume_context: str = Field(default="", max_length=12_000)


class ResumeResponse(BaseModel):
    filename: str
    resume_context: str


class StartInterviewResponse(BaseModel):
    attempt_id: str
    conversation_id: str
    dailyRoom: str
    dailyToken: str


class TranscriptEntry(BaseModel):
    speaker: Literal["candidate", "interviewer"]
    text: str = Field(min_length=1, max_length=10_000)
    timestamp: str | None = None


class CompleteInterviewRequest(BaseModel):
    transcript: list[TranscriptEntry] = Field(max_length=500)


class InterviewAnalysis(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    communication_clarity_score: int = Field(ge=0, le=100)
    answer_structure_score: int = Field(ge=0, le=100)
    role_knowledge_score: int = Field(ge=0, le=100)
    analytical_reasoning_score: int = Field(ge=0, le=100)
    evidence_specificity_score: int = Field(ge=0, le=100)
    strengths: list[str]
    improvement_areas: list[str]
    recommended_next_steps: list[str]
    summary: str


class InterviewReport(BaseModel):
    status: Literal["pending_provider", "ready"]
    message: str
    analysis: InterviewAnalysis | None = None


class InterviewAttemptResponse(BaseModel):
    attempt_id: str
    conversation_id: str
    status: Literal["active", "completed"]
    brief: StartInterviewRequest
    transcript: list[TranscriptEntry]
    report: InterviewReport | None = None


class ClientConfig(BaseModel):
    configured: bool

