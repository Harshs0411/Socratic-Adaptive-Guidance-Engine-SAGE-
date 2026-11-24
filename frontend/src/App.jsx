import React, { useState, useEffect, useCallback } from "react";
import TopicSelection from "./components/TopicSelection";
import Workspace from "./components/Workspace";
import { AlertCircle, X } from "lucide-react";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api";

function getOrCreateStudentId() {
  let id = localStorage.getItem("sage_student_id");
  if (!id) {
    id = "student_" + Math.random().toString(36).substring(2, 10);
    localStorage.setItem("sage_student_id", id);
  }
  return id;
}

export default function App() {
  const [session, setSession] = useState(null);
  const [pastSessions, setPastSessions] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState(null);

  // Load previous sessions for student from backend
  const fetchPastSessions = useCallback(async () => {
    try {
      const studentId = getOrCreateStudentId();
      const res = await fetch(`${API_BASE}/sessions/student/${studentId}`);
      if (res.ok) {
        const data = await res.json();
        setPastSessions(data.sessions || []);
      }
    } catch (err) {
      console.warn("Could not load previous sessions:", err);
    }
  }, []);

  // Check for saved active session on load
  useEffect(() => {
    fetchPastSessions();
    const savedSessionId = localStorage.getItem("sage_active_session_id");
    if (savedSessionId) {
      setIsLoading(true);
      fetch(`${API_BASE}/session/${savedSessionId}`)
        .then((res) => {
          if (res.ok) return res.json();
          throw new Error("Session expired or not found");
        })
        .then((data) => {
          setSession(data);
        })
        .catch(() => {
          localStorage.removeItem("sage_active_session_id");
        })
        .finally(() => {
          setIsLoading(false);
        });
    }
  }, [fetchPastSessions]);

  // Start new learning session
  const handleStartSession = async (topic, depthLevel = "deep", selfReportedLevel = null, startFresh = false) => {
    if (isLoading) return;
    setIsLoading(true);
    setError(null);
    try {
      const payload = {
        topic,
        student_id: getOrCreateStudentId(),
        depth_level: depthLevel,
        start_fresh: Boolean(startFresh),
      };
      if (selfReportedLevel) {
        payload.self_reported_level = selfReportedLevel;
      }

      const res = await fetch(`${API_BASE}/session/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Server error: ${res.status}`);
      }

      const data = await res.json();
      setSession(data);
      if (data?.session_id) {
        localStorage.setItem("sage_active_session_id", data.session_id);
      }
      fetchPastSessions();
    } catch (err) {
      console.error("Failed to start session:", err);
      setError(`Failed to initialize session: ${err.message}. Make sure the FastAPI backend is running.`);
    } finally {
      setIsLoading(false);
    }
  };

  // Resume a past session by ID
  const handleSelectPastSession = async (sessionId) => {
    if (!sessionId || isLoading || session?.session_id === sessionId) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/session/${sessionId}`);
      if (!res.ok) {
        throw new Error("Session could not be loaded");
      }
      const data = await res.json();
      setSession(data);
      localStorage.setItem("sage_active_session_id", sessionId);
    } catch (err) {
      setError(`Failed to resume session: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Send student response
  const handleSendMessage = async (message) => {
    if (!session || isSending) return;
    setIsSending(true);
    setError(null);

    // Optimistically update chat history with user message
    const tempUserMsg = {
      id: "temp-" + Date.now(),
      role: "user",
      content: message,
    };
    setSession((prev) => ({
      ...prev,
      chat_history: [...prev.chat_history, tempUserMsg],
    }));

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "text/event-stream, application/json",
        },
        body: JSON.stringify({
          session_id: session.session_id,
          message,
          stream: true,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Server error: ${res.status}`);
      }

      const contentType = res.headers.get("content-type") || "";

      // Real-Time SSE Stream Consumption
      if (contentType.includes("text/event-stream") && res.body) {
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        const streamMsgId = "asst-stream-" + Date.now();
        let accumulatedContent = "";
        let lastRenderTime = 0;
        const RENDER_THROTTLE_MS = 50;

        const flushStreamingUi = (force = false) => {
          const now = performance.now();
          if (force || now - lastRenderTime >= RENDER_THROTTLE_MS) {
            lastRenderTime = now;
            setSession((prev) => {
              if (!prev) return prev;
              const history = [...prev.chat_history];
              const existingIdx = history.findIndex((m) => m.id === streamMsgId);
              const streamMsg = {
                id: streamMsgId,
                role: "assistant",
                content: accumulatedContent,
                isStreaming: true,
              };
              if (existingIdx >= 0) {
                history[existingIdx] = streamMsg;
              } else {
                history.push(streamMsg);
              }
              return { ...prev, chat_history: history };
            });
          }
        };

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop() || "";

          for (const part of parts) {
            const lines = part.split("\n");
            let eventType = "token";
            let eventData = "";

            for (const line of lines) {
              if (line.startsWith("event: ")) {
                eventType = line.slice(7).trim();
              } else if (line.startsWith("data: ")) {
                eventData = line.slice(6);
              }
            }

            if (!eventData) continue;

            if (eventType === "token") {
              try {
                const parsed = JSON.parse(eventData);
                const delta = parsed.delta !== undefined ? parsed.delta : (parsed.token !== undefined ? parsed.token : "");
                accumulatedContent += delta;
                flushStreamingUi(false);
              } catch (e) {
                // If data was raw string instead of json
                accumulatedContent += eventData;
                flushStreamingUi(false);
              }
            } else if (eventType === "done") {
              flushStreamingUi(true);
              try {
                const finalData = JSON.parse(eventData);
                setSession((prev) => ({
                  ...prev,
                  chat_history: finalData.chat_history,
                  curriculum: finalData.curriculum,
                  mermaid_dag: finalData.mermaid_dag,
                  mastery: finalData.mastery,
                  active_concept: finalData.active_concept,
                  phase: finalData.phase,
                  is_graduated: finalData.is_graduated,
                  hake_gain: finalData.hake_gain,
                  overall_progress: finalData.overall_progress ?? prev.overall_progress,
                  teaching_mode: finalData.teaching_mode ?? prev.teaching_mode,
                  doubts_asked: finalData.doubts_asked ?? prev.doubts_asked,
                  visuals: finalData.visuals ?? prev.visuals,
                }));
                fetchPastSessions();
              } catch (e) {
                console.error("Failed to parse done event:", e);
              }
            } else if (eventType === "error") {
              try {
                const errObj = JSON.parse(eventData);
                throw new Error(errObj.error || "Streaming error from SAGE tutor");
              } catch (e) {
                throw new Error(eventData);
              }
            }
          }
        }
      } else {
        // Fallback for non-streaming standard JSON response
        const data = await res.json();
        setSession((prev) => ({
          ...prev,
          chat_history: data.chat_history,
          curriculum: data.curriculum,
          mermaid_dag: data.mermaid_dag,
          mastery: data.mastery,
          active_concept: data.active_concept,
          phase: data.phase,
          is_graduated: data.is_graduated,
          hake_gain: data.hake_gain,
          overall_progress: data.overall_progress ?? prev.overall_progress,
          teaching_mode: data.teaching_mode ?? prev.teaching_mode,
          doubts_asked: data.doubts_asked ?? prev.doubts_asked,
          visuals: data.visuals ?? prev.visuals,
        }));
        fetchPastSessions();
      }
    } catch (err) {
      console.error("Failed to send message:", err);
      setError(`Failed to send message: ${err.message}`);
    } finally {
      setIsSending(false);
    }
  };

  const handleUploadDoc = async (file) => {
    if (!session) return;
    const formData = new FormData();
    formData.append("session_id", session.session_id);
    formData.append("file", file);

    const res = await fetch(`${API_BASE}/documents/upload`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Upload failed with status ${res.status}`);
    }

    return await res.json();
  };

  const handleDrilldown = async (conceptId) => {
    if (!session) return;
    setIsSending(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/session/drilldown`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: session.session_id,
          concept_id: conceptId,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Drilldown failed with status ${res.status}`);
      }

      const data = await res.json();
      setSession((prev) => ({
        ...prev,
        curriculum: data.curriculum,
        mermaid_dag: data.mermaid_dag,
        mastery: data.mastery,
        overall_progress: data.overall_progress ?? prev.overall_progress,
        active_concept: data.active_concept,
        chat_history: data.chat_history || prev.chat_history,
      }));
    } catch (err) {
      console.error("Failed to drilldown:", err);
      setError(`Failed to drill down into concept: ${err.message}`);
    } finally {
      setIsSending(false);
    }
  };

  const handleNewSession = () => {
    setSession(null);
    setError(null);
  };

  const handleReset = async () => {
    if (session?.session_id) {
      fetch(`${API_BASE}/session/reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: session.session_id }),
      }).catch(() => {});
    }
    localStorage.removeItem("sage_active_session_id");
    setSession(null);
    setError(null);
    fetchPastSessions();
  };

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "var(--bg-app)", color: "var(--text-primary)" }}>
      {/* Refined Toast Notification */}
      {error && (
        <div 
          style={{
            position: "fixed",
            top: "1.25rem",
            right: "1.25rem",
            zIndex: 100,
            maxWidth: "460px",
            backgroundColor: "#fef2f2",
            color: "#991b1b",
            padding: "0.85rem 1.15rem",
            borderRadius: "0.75rem",
            border: "1px solid #fecaca",
            boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.1)",
            fontSize: "0.875rem",
            display: "flex",
            alignItems: "flex-start",
            gap: "0.75rem",
          }}
        >
          <AlertCircle size={18} style={{ flexShrink: 0, marginTop: "2px", color: "#dc2626" }} />
          <div style={{ flex: 1, lineHeight: "1.4", fontWeight: "500" }}>{error}</div>
          <button 
            onClick={() => setError(null)} 
            style={{ background: "none", border: "none", color: "#991b1b", cursor: "pointer", padding: "0 0.2rem" }}
          >
            <X size={16} />
          </button>
        </div>
      )}

      {!session ? (
        <TopicSelection 
          onStart={handleStartSession} 
          isLoading={isLoading} 
          pastSessions={pastSessions}
          onResumeSession={handleSelectPastSession}
        />
      ) : (
        <Workspace
          sessionData={session}
          pastSessions={pastSessions}
          onSendMessage={handleSendMessage}
          onUploadDoc={handleUploadDoc}
          onDrilldown={handleDrilldown}
          onReset={handleReset}
          onNewSession={handleNewSession}
          onResumeSession={handleSelectPastSession}
          isSending={isSending}
        />
      )}
    </div>
  );
}
