from dataclasses import dataclass, field
from threading import Lock
from uuid import uuid4

from fastapi import HTTPException, status

from app.schemas import InterviewAnalysis, InterviewReport, StartInterviewRequest, TranscriptEntry


@dataclass
class InterviewAttempt:
    attempt_id: str
    brief: StartInterviewRequest
    conversation_id: str = ""
    status: str = "active"
    transcript: list[TranscriptEntry] = field(default_factory=list)
    report: InterviewReport | None = None


class AttemptStore:
    """Prototype-only in-memory storage; production LRN will use MongoDB."""

    def __init__(self) -> None:
        self._attempts: dict[str, InterviewAttempt] = {}
        self._lock = Lock()

    def create(self, brief: StartInterviewRequest) -> InterviewAttempt:
        attempt = InterviewAttempt(attempt_id=str(uuid4()), brief=brief)
        with self._lock:
            self._attempts[attempt.attempt_id] = attempt
        return attempt

    def attach_conversation(self, attempt_id: str, conversation_id: str) -> InterviewAttempt:
        attempt = self.get(attempt_id)
        with self._lock:
            attempt.conversation_id = conversation_id
        return attempt

    def remove(self, attempt_id: str) -> None:
        with self._lock:
            self._attempts.pop(attempt_id, None)

    def get(self, attempt_id: str) -> InterviewAttempt:
        with self._lock:
            attempt = self._attempts.get(attempt_id)
        if attempt is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found.")
        return attempt

    def complete(
        self,
        attempt_id: str,
        transcript: list[TranscriptEntry],
        analysis: InterviewAnalysis | None = None,
    ) -> InterviewAttempt:
        attempt = self.get(attempt_id)
        with self._lock:
            # Completion is retry-safe: the latest full client transcript replaces the prior copy.
            attempt.transcript = self._merge_consecutive_speakers(transcript)
            attempt.status = "completed"
            attempt.report = (
                InterviewReport(status="ready", message="EIGI call analysis is ready.", analysis=analysis)
                if analysis
                else InterviewReport(
                    status="pending_provider",
                    message="Transcript saved. EIGI call analysis is not available yet.",
                )
            )
        return attempt

    def attach_analysis(self, attempt_id: str, analysis: InterviewAnalysis) -> InterviewAttempt:
        attempt = self.get(attempt_id)
        with self._lock:
            attempt.report = InterviewReport(
                status="ready",
                message="EIGI call analysis is ready.",
                analysis=analysis,
            )
        return attempt

    @staticmethod
    def _merge_consecutive_speakers(transcript: list[TranscriptEntry]) -> list[TranscriptEntry]:
        merged: list[TranscriptEntry] = []
        for entry in transcript:
            if merged and merged[-1].speaker == entry.speaker:
                merged[-1] = TranscriptEntry(
                    speaker=entry.speaker,
                    text=f"{merged[-1].text.rstrip()} {entry.text.lstrip()}",
                    timestamp=merged[-1].timestamp or entry.timestamp,
                )
            else:
                merged.append(entry.model_copy())
        return merged


attempt_store = AttemptStore()
