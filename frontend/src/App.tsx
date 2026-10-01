import { PipecatClient } from "@pipecat-ai/client-js";
import { PipecatClientAudio, PipecatClientProvider } from "@pipecat-ai/client-react";
import { DailyTransport } from "@pipecat-ai/daily-transport";
import { useEffect, useMemo, useState } from "react";

import {
  completeInterview,
  createInterview,
  getConfiguration,
  getInterview,
  uploadResume,
  type InterviewAttempt,
  type InterviewBrief,
  type TranscriptEntry,
} from "./api";

type Screen = "prepare" | "live" | "review";

const initialBrief: InterviewBrief = {
  target_role: "Investment banking",
  focus_area: "Valuation",
  interview_mode: "realistic",
  duration_minutes: 15,
  resume_context: "",
};

export default function App() {
  const [screen, setScreen] = useState<Screen>("prepare");
  const [brief, setBrief] = useState(initialBrief);
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [transportState, setTransportState] = useState("disconnected");
  const [muted, setMuted] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState("");
  const [attemptId, setAttemptId] = useState("");
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const [completedAttempt, setCompletedAttempt] = useState<InterviewAttempt | null>(null);

  const client = useMemo(
    () =>
      new PipecatClient({
        transport: new DailyTransport({ bufferLocalAudioUntilBotReady: true }),
        enableMic: true,
        enableCam: false,
        callbacks: {
          onTransportStateChanged: (state) => setTransportState(String(state)),
          onUserTranscript: (data) => {
            if (!data.final || !data.text.trim()) return;
            setTranscript((current) => [
              ...current,
              { speaker: "candidate", text: data.text.trim(), timestamp: data.timestamp },
            ]);
          },
          onBotTranscript: (data) => {
            if (!data.text.trim()) return;
            setTranscript((current) => [
              ...current,
              { speaker: "interviewer", text: data.text.trim() },
            ]);
          },
        },
      }),
    [],
  );

  useEffect(() => {
    getConfiguration().then(setConfigured).catch((reason: Error) => setError(reason.message));
    return () => {
      void client.disconnect();
    };
  }, [client]);

  useEffect(() => {
    if (screen !== "review" || !attemptId || completedAttempt?.report?.status !== "pending_provider") return;
    let cancelled = false;
    let checks = 0;
    const poll = async () => {
      if (cancelled || checks++ >= 15) return;
      try {
        const current = await getInterview(attemptId);
        if (cancelled) return;
        setCompletedAttempt(current);
        if (current.report?.status !== "ready") window.setTimeout(poll, 2000);
      } catch {
        if (!cancelled) window.setTimeout(poll, 2000);
      }
    };
    const timeout = window.setTimeout(poll, 2000);
    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
    };
  }, [attemptId, completedAttempt?.report?.status, screen]);

  async function start() {
    setConnecting(true);
    setError("");
    try {
      const session = await createInterview(brief);
      setAttemptId(session.attempt_id);
      setTranscript([]);
      setCompletedAttempt(null);
      setScreen("live");
      void client.connect({ url: session.dailyRoom, token: session.dailyToken }).catch((reason) => {
        setError(reason instanceof Error ? reason.message : "Could not connect to the interviewer.");
        setScreen("prepare");
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not start the interview.");
    } finally {
      setConnecting(false);
    }
  }

  function toggleMute() {
    const nextEnabled = !client.isMicEnabled;
    client.enableMic(nextEnabled);
    setMuted(!nextEnabled);
  }

  async function end() {
    setError("");
    try {
      await client.disconnect();
      const result = await completeInterview(attemptId, transcript);
      setCompletedAttempt(result);
      setScreen("review");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save this interview.");
    } finally {
      setMuted(false);
    }
  }

  function reset() {
    setAttemptId("");
    setTranscript([]);
    setCompletedAttempt(null);
    setScreen("prepare");
  }

  return (
    <PipecatClientProvider client={client}>
      <a className="skip" href="#content">Skip to content</a>
      <aside>
        <div className="brand">LRN.<small>INTERVIEW READINESS</small></div>
        <nav aria-label="Workspace">
          <span>Dashboard</span><span>Diagnostic</span><span>Practice</span>
          <strong>Voice interview</strong>
        </nav>
      </aside>
      <div className="shell">
        <header><span className="muted">Workspace / </span> Voice interview</header>
        <main id="content">
          {error && screen !== "prepare" && <div className="error" role="alert">{error}</div>}
          {screen === "prepare" ? (
            <Prepare
              brief={brief}
              configured={configured}
              connecting={connecting}
              error={error}
              onChange={setBrief}
              onStart={start}
            />
          ) : screen === "live" ? (
            <Live
              brief={brief}
              transportState={transportState}
              muted={muted}
              onMute={toggleMute}
              onEnd={end}
            />
          ) : completedAttempt ? (
            <Review attempt={completedAttempt} onReset={reset} />
          ) : null}
        </main>
      </div>
      <PipecatClientAudio />
    </PipecatClientProvider>
  );
}

function Review({ attempt, onReset }: { attempt: InterviewAttempt; onReset: () => void }) {
  return (
    <>
      <div className="title live-title">
        <div><h1>Interview review</h1><p className="muted">{attempt.brief.target_role} · {attempt.brief.focus_area}</p></div>
        <button onClick={onReset}>Start another</button>
      </div>
      <div className="grid review-grid">
        <section className="panel">
          <h2>Transcript</h2>
          {attempt.transcript.length === 0 ? <p className="muted">No final transcript segments were received from the voice provider.</p> : (
            <div className="transcript">
              {attempt.transcript.map((entry, index) => (
                <article key={`${entry.speaker}-${index}`}>
                  <strong>{entry.speaker === "candidate" ? "You" : "Interviewer"}</strong>
                  <p>{entry.text}</p>
                </article>
              ))}
            </div>
          )}
        </section>
        <section className="panel">
          <h2>Report</h2>
          <p className="muted">{attempt.report?.message}</p>
          {attempt.report?.analysis ? (
            <dl className="analysis">
              {Object.entries(attempt.report.analysis).map(([label, value]) => (
                <div key={label}><dt>{label.replaceAll("_", " ")}</dt><dd>{Array.isArray(value) ? <ul>{value.map((item) => <li key={String(item)}>{String(item)}</li>)}</ul> : String(value)}</dd></div>
              ))}
            </dl>
          ) : (
            <p className="report-note">EIGI is generating your structured interview analysis. It will appear here automatically.</p>
          )}
        </section>
      </div>
    </>
  );
}

function Prepare({ brief, configured, connecting, error, onChange, onStart }: {
  brief: InterviewBrief;
  configured: boolean | null;
  connecting: boolean;
  error: string;
  onChange: (value: InterviewBrief) => void;
  onStart: () => void;
}) {
  const [consent, setConsent] = useState(false);
  const [resumeName, setResumeName] = useState("");
  const [uploadingResume, setUploadingResume] = useState(false);
  const [resumeError, setResumeError] = useState("");
  const update = <K extends keyof InterviewBrief>(key: K, value: InterviewBrief[K]) =>
    onChange({ ...brief, [key]: value });

  async function chooseResume(file?: File) {
    if (!file) return;
    setUploadingResume(true);
    setResumeError("");
    try {
      const result = await uploadResume(file);
      setResumeName(result.filename);
      update("resume_context", result.resume_context);
    } catch (reason) {
      setResumeName("");
      update("resume_context", "");
      setResumeError(reason instanceof Error ? reason.message : "Could not read this resume.");
    } finally {
      setUploadingResume(false);
    }
  }

  return (
    <>
      <div className="title"><h1>Make your thinking heard.</h1><p className="muted">A focused mock interview with natural voice interaction and actionable feedback.</p></div>
      {configured === false && <div className="banner">EIGI credentials are pending. The interface is ready, but a live call cannot start yet.</div>}
      {error && <div className="error" role="alert">{error}</div>}
      <div className="grid">
        <section className="panel">
          <h2>Set your interview brief</h2>
          <div className="resume-upload">
            <div><strong>Resume</strong><p className="muted">Optional · PDF or DOCX · up to 5 MB. Used for the opening interview questions.</p></div>
            <label className="upload-button">{uploadingResume ? "Reading…" : resumeName ? "Replace" : "Upload resume"}<input type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" disabled={uploadingResume} onChange={(event) => void chooseResume(event.target.files?.[0])} /></label>
            {resumeName && <div className="resume-ready"><span>{resumeName}</span><button type="button" onClick={() => { setResumeName(""); update("resume_context", ""); }}>Remove</button></div>}
            {resumeError && <p className="error" role="alert">{resumeError}</p>}
          </div>
          <div className="fields">
            <Field label="Target role" value={brief.target_role} values={["Investment banking", "Private equity", "Consulting"]} onChange={(v) => update("target_role", v)} />
            <Field label="Focus area" value={brief.focus_area} values={["Valuation", "Accounting", "LBO mechanics", "M&A", "Behavioural"]} onChange={(v) => update("focus_area", v)} />
            <Field label="Interview format" value={brief.interview_mode} values={["realistic", "guided"]} onChange={(v) => update("interview_mode", v as "realistic" | "guided")} />
            <Field label="Session length" value={String(brief.duration_minutes)} values={["15", "30"]} onChange={(v) => update("duration_minutes", Number(v) as 15 | 30)} />
          </div>
          <label className="consent"><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} /> <span>I understand that this AI interview will process my voice and create a transcript for feedback.</span></label>
          <button className="primary" disabled={!consent || configured !== true || connecting || uploadingResume} onClick={onStart}>{connecting ? "Connecting…" : "Start voice interview →"}</button>
        </section>
        <section className="panel steps"><h2>What happens next</h2><p><b>1.</b> Explain your approach naturally.</p><p><b>2.</b> Respond to focused follow-up questions.</p><p><b>3.</b> Review answer-level feedback.</p></section>
      </div>
    </>
  );
}

function Field({ label, value, values, onChange }: { label: string; value: string; values: string[]; onChange: (value: string) => void }) {
  return <label>{label}<select value={value} onChange={(e) => onChange(e.target.value)}>{values.map((item) => <option key={item} value={item}>{item[0].toUpperCase() + item.slice(1)}</option>)}</select></label>;
}

function Live({ brief, transportState, muted, onMute, onEnd }: { brief: InterviewBrief; transportState: string; muted: boolean; onMute: () => void; onEnd: () => Promise<void> }) {
  return (
    <>
      <div className="title live-title"><div><h1>{brief.focus_area} interview</h1><p className="muted">{brief.target_role} · {brief.duration_minutes} minutes</p></div><button onClick={() => void onEnd()}>End interview</button></div>
      <section className="panel session">
        <div className="status"><i /> {transportState}</div>
        <div className="voice-ring" aria-hidden="true"><span /></div>
        <h2>The interviewer is connected</h2>
        <p className="muted">Speak naturally. You can interrupt the interviewer or pause before answering.</p>
        <div className="controls"><button className={muted ? "primary" : ""} onClick={onMute}>{muted ? "Unmute microphone" : "Mute microphone"}</button><button onClick={() => void onEnd()}>End & review</button></div>
      </section>
    </>
  );
}

