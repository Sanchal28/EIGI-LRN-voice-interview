export type InterviewBrief = {
  target_role: string;
  focus_area: string;
  interview_mode: "realistic" | "guided";
  duration_minutes: 15 | 30;
  resume_context: string;
};

export type VoiceSession = {
  attempt_id: string;
  conversation_id: string;
  dailyRoom: string;
  dailyToken: string;
};

export type TranscriptEntry = {
  speaker: "candidate" | "interviewer";
  text: string;
  timestamp?: string;
};

export type InterviewAttempt = {
  attempt_id: string;
  conversation_id: string;
  status: "active" | "completed";
  brief: InterviewBrief;
  transcript: TranscriptEntry[];
  report: null | {
    status: "pending_provider" | "ready";
    message: string;
    analysis?: Record<string, unknown> | null;
  };
};

async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    return body.detail || "Request failed.";
  } catch {
    return "Request failed.";
  }
}

export async function getConfiguration(): Promise<boolean> {
  const response = await fetch("/api/config");
  if (!response.ok) throw new Error(await readError(response));
  return ((await response.json()) as { configured: boolean }).configured;
}

export async function createInterview(brief: InterviewBrief): Promise<VoiceSession> {
  const response = await fetch("/api/interviews", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(brief),
  });
  if (!response.ok) throw new Error(await readError(response));
  return response.json() as Promise<VoiceSession>;
}

export async function uploadResume(file: File): Promise<{ filename: string; resume_context: string }> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch("/api/resume", { method: "POST", body });
  if (!response.ok) throw new Error(await readError(response));
  return response.json() as Promise<{ filename: string; resume_context: string }>;
}

export async function completeInterview(
  attemptId: string,
  transcript: TranscriptEntry[],
): Promise<InterviewAttempt> {
  const response = await fetch(`/api/interviews/${attemptId}/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transcript }),
  });
  if (!response.ok) throw new Error(await readError(response));
  return response.json() as Promise<InterviewAttempt>;
}

export async function getInterview(attemptId: string): Promise<InterviewAttempt> {
  const response = await fetch(`/api/interviews/${attemptId}`);
  if (!response.ok) throw new Error(await readError(response));
  return response.json() as Promise<InterviewAttempt>;
}

