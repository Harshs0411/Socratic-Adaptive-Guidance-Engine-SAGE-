import React, { useState, useEffect } from "react";
import TopicSelection from "./components/TopicSelection";
import Workspace from "./components/Workspace";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api";

export default function App() {
  const [session, setSession] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
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
  }, []);

  const handleStartSession = async (topic, depthLevel = "deep", selfReportedLevel = null) => {
    setIsLoading(true);
    setError(null);
    try {
      const payload = {
        topic,
        student_id: "student_001",
        depth_level: depthLevel,
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
    } catch (err) {
      console.error("Failed to start session:", err);
      setError(`Failed to initialize session: ${err.message}. Make sure the FastAPI backend is running on port 8000.`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendMessage = async (message) => {
    if (!session) return;
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
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: session.session_id,
          message,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Server error: ${res.status}`);
      }

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
        teaching_mode: data.teaching_mode ?? prev.teaching_mode,
        doubts_asked: data.doubts_asked ?? prev.doubts_asked,
        visuals: data.visuals ?? prev.visuals,
      }));
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
  };

  return (
    <div style={{ minHeight: "100vh", backgroundColor: "#0b0f19" }}>
      {error && (
        <div style={{ backgroundColor: "#991b1b", color: "#fef2f2", padding: "0.75rem 1.5rem", fontSize: "0.875rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>⚠️ {error}</span>
          <button onClick={() => setError(null)} style={{ background: "none", border: "none", color: "#fecaca", cursor: "pointer", fontWeight: "700" }}>✕</button>
        </div>
      )}

      {!session ? (
        <TopicSelection onStart={handleStartSession} isLoading={isLoading} />
      ) : (
        <Workspace
          sessionData={session}
          onSendMessage={handleSendMessage}
          onUploadDoc={handleUploadDoc}
          onDrilldown={handleDrilldown}
          onReset={handleReset}
          isSending={isSending}
        />
      )}
    </div>
  );
}
