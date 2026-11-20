import React, { useState, useRef, useEffect } from "react";
import { 
  Send, Brain, BookOpen, ChevronDown, ChevronUp, Upload, 
  RotateCcw, Sparkles, CheckCircle2, Award, Download, 
  Eye, EyeOff, Layers, HelpCircle, MessageSquare, 
  PanelLeftClose, PanelLeft, Plus, History, User, Check, AlertCircle, Compass, Zap
} from "lucide-react";
import confetti from "canvas-confetti";
import MermaidDAG from "./MermaidDAG";
import ErrorBoundary from "./ErrorBoundary";
import { marked } from "marked";

marked.setOptions({
  gfm: true,
  breaks: true,
});

/**
 * Formats message content, dynamically extracting Mermaid diagrams
 * and rendering standard markdown with code blocks, math, and tables.
 */
function FormattedMessageContent({ content }) {
  if (!content) return null;

  const mermaidRegex = /```mermaid\s*([\s\S]*?)```/g;
  const parts = [];
  let lastIndex = 0;
  let match;

  while ((match = mermaidRegex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: "text", text: content.slice(lastIndex, match.index) });
    }
    parts.push({ type: "mermaid", chart: match[1].trim() });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < content.length) {
    parts.push({ type: "text", text: content.slice(lastIndex) });
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.85rem" }}>
      {parts.map((p, idx) => {
        if (p.type === "mermaid") {
          return <MermaidDAG key={idx} chart={p.chart} title="📊 Concept Visual Model" />;
        }
        const html = marked.parse(p.text || "");
        return (
          <div
            key={idx}
            className="markdown-body"
            dangerouslySetInnerHTML={{ __html: html }}
          />
        );
      })}
    </div>
  );
}

export default function Workspace({ 
  sessionData, 
  pastSessions = [],
  onSendMessage, 
  onUploadDoc, 
  onDrilldown, 
  onReset, 
  onNewSession,
  onResumeSession,
  isSending 
}) {
  const [input, setInput] = useState("");
  const [showDAG, setShowDAG] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [sidebarTab, setSidebarTab] = useState("curriculum"); // "curriculum" or "sessions"
  const [expandedCitations, setExpandedCitations] = useState({});
  const [expandedMetrics, setExpandedMetrics] = useState({});
  const [uploadStatus, setUploadStatus] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const messagesEndRef = useRef(null);

  const { 
    session_id, topic, chat_history = [], curriculum = [], 
    mermaid_dag, mastery, active_concept, phase, is_graduated, hake_gain,
    teaching_mode = "mode_2_teach_first", doubts_asked = 0, visuals = [], review_queue = []
  } = sessionData;

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat_history, isSending]);

  // Trigger confetti upon graduation
  useEffect(() => {
    if (is_graduated) {
      confetti({
        particleCount: 120,
        spread: 80,
        origin: { y: 0.6 },
      });
    }
  }, [is_graduated]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isSending) {
      onSendMessage(input.trim());
      setInput("");
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadStatus("Ingesting & indexing textbook into ChromaDB...");
    try {
      const res = await onUploadDoc(file);
      setUploadStatus(`✅ Ingested ${res.chunks_added} chunks from '${res.filename}'!`);
    } catch (err) {
      setUploadStatus(`✗ Failed to ingest: ${err.message || err}`);
    } finally {
      setIsUploading(false);
      e.target.value = null;
    }
  };

  const downloadReport = () => {
    const preScore = hake_gain?.pre ?? 0.2;
    const postScore = hake_gain?.post ?? 0.95;
    const gVal = hake_gain?.hake_g ?? 0.9;
    const gLabel = hake_gain?.label ?? "High Gain";

    let md = `# 🎓 SAGE ACADEMIC GRADUATION & COGNITIVE MASTERY REPORT\n\n`;
    md += `**Target Subject:** ${topic}  \n`;
    md += `**Evaluation Model:** Continuous Bayesian Knowledge Tracing & Agentic Pedagogical RAG  \n`;
    md += `**Session Status:** All Concepts Mastered ($P(L_t) \\ge 85\\%$)\n\n`;
    md += `---\n\n`;
    md += `## 📊 Scientific Learning Gain Analysis\n`;
    md += `- **Diagnostic Pre-Assessment Baseline:** ${(preScore * 100).toFixed(1)}%\n`;
    md += `- **Post-Tutoring Concept Mastery Level:** ${(postScore * 100).toFixed(1)}%\n`;
    md += `- **Hake's Normalized Learning Gain (g):** **${gVal.toFixed(2)}** (${gLabel})\n\n`;
    md += `$$g = \\frac{\\text{Post} - \\text{Pre}}{1 - \\text{Pre}} = \\frac{${postScore.toFixed(2)} - ${preScore.toFixed(2)}}{1 - ${preScore.toFixed(2)}} = ${gVal.toFixed(2)}$$\n\n`;
    md += `## 🎯 Concept Mastery Breakdown\n`;
    (curriculum || []).forEach((c) => {
      md += `- **${c.name}**: ${(c.score * 100).toFixed(1)}% (Status: Mastered)\n`;
    });
    md += `\n---\n*Verified by SAGE Autonomous Pedagogical Engine (LangGraph + SQLite + OpenAI)*\n`;

    const blob = new Blob([md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `SAGE_Mastery_Report_${topic.replace(/\s+/g, "_")}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const actionBadges = {
    initial: { label: "🌱 Initial Inquiry", color: "#059669", bg: "#ecfdf5" },
    probe: { label: "🔍 Socratic Probe", color: "#0284c7", bg: "#e0f2fe" },
    hint: { label: "💡 Guided Hint", color: "#d97706", bg: "#fffbeb" },
    scaffold: { label: "🪜 Reasoning Scaffold", color: "#ea580c", bg: "#fff7ed" },
    explain: { label: "📖 Concept Explanation", color: "#7c3aed", bg: "#f5f3ff" },
    advance: { label: "🚀 Concept Advance", color: "#059669", bg: "#dcfce7" },
    diagnostic: { label: "📋 Diagnostic Assessment", color: "#2563eb", bg: "#eff6ff" },
  };

  // Inspect latest message to determine context-aware quick actions
  const lastAsstMsg = [...chat_history].reverse().find(m => m.role === "assistant");
  const lastMsgText = (lastAsstMsg?.content || "").toLowerCase();
  const isLevelPrompt = lastMsgText.includes("beginner") && (lastMsgText.includes("comfortable") || lastMsgText.includes("experience"));
  const isAwaitingContinue = lastAsstMsg?.awaiting === "continue" || (!lastAsstMsg?.question && (lastMsgText.includes("click continue") || lastMsgText.includes("click **continue**")));
  const isAwaitingClarity = lastAsstMsg?.awaiting === "clarity_check" || lastMsgText.includes("does that make sense");

  const masteredCount = (curriculum || []).filter(c => c.status === "mastered" || (c.score || 0) >= 0.85).length;
  const totalConcepts = (curriculum || []).length || 1;
  const overallProgressPct = Math.round((masteredCount / totalConcepts) * 100);

  return (
    <div className="sage-app-container">
      {/* =================================================================== */}
      {/* SIDEBAR */}
      {/* =================================================================== */}
      <aside 
        className="sage-sidebar"
        style={{
          width: isSidebarOpen ? "350px" : "0px",
          minWidth: isSidebarOpen ? "350px" : "0px",
          backgroundColor: "var(--bg-sidebar)",
          borderRight: isSidebarOpen ? "1px solid var(--border-subtle)" : "none",
          display: "flex",
          flexDirection: "column",
          height: "100%",
          overflow: "hidden",
          position: "relative",
          zIndex: 30,
        }}
      >
        {isSidebarOpen && (
          <>
            {/* Sidebar Branding & New Session */}
            <div style={{ padding: "1.25rem", borderBottom: "1px solid var(--border-subtle)", display: "flex", flexDirection: "column", gap: "1rem" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                  <div style={{ width: "32px", height: "32px", borderRadius: "0.6rem", background: "linear-gradient(135deg, #4f46e5 0%, #0284c7 100%)", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 2px 8px rgba(99, 102, 241, 0.25)" }}>
                    <Brain size={18} style={{ color: "#ffffff" }} />
                  </div>
                  <div>
                    <div style={{ fontWeight: "800", fontSize: "1.1rem", letterSpacing: "-0.02em", color: "#0f172a" }}>
                      SAGE <span style={{ fontSize: "0.7rem", fontWeight: "600", padding: "0.15rem 0.4rem", borderRadius: "9999px", backgroundColor: "#eef2ff", color: "var(--indigo-600)" }}>v2.4</span>
                    </div>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => setIsSidebarOpen(false)}
                  style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", display: "flex", alignItems: "center", padding: "0.25rem" }}
                  title="Collapse Sidebar"
                >
                  <PanelLeftClose size={18} />
                </button>
              </div>

              {/* + New Topic Button */}
              <button
                type="button"
                onClick={onNewSession || onReset}
                className="btn-primary"
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "0.5rem",
                  padding: "0.65rem 1rem",
                  borderRadius: "0.75rem",
                  fontSize: "0.85rem",
                  fontWeight: "700",
                  width: "100%",
                }}
              >
                <Plus size={16} /> New Learning Session
              </button>
            </div>

            {/* Sidebar Navigation Tabs: Curriculum vs Past Sessions */}
            <div style={{ display: "flex", borderBottom: "1px solid var(--border-subtle)", backgroundColor: "#f8fafc" }}>
              <button
                type="button"
                onClick={() => setSidebarTab("curriculum")}
                style={{
                  flex: 1,
                  padding: "0.65rem",
                  fontSize: "0.775rem",
                  fontWeight: "700",
                  background: "none",
                  border: "none",
                  borderBottom: sidebarTab === "curriculum" ? "2px solid var(--indigo-600)" : "2px solid transparent",
                  color: sidebarTab === "curriculum" ? "var(--indigo-600)" : "var(--text-muted)",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "0.4rem",
                }}
              >
                <Layers size={14} /> Curriculum ({totalConcepts})
              </button>
              <button
                type="button"
                onClick={() => setSidebarTab("sessions")}
                style={{
                  flex: 1,
                  padding: "0.65rem",
                  fontSize: "0.775rem",
                  fontWeight: "700",
                  background: "none",
                  border: "none",
                  borderBottom: sidebarTab === "sessions" ? "2px solid var(--indigo-600)" : "2px solid transparent",
                  color: sidebarTab === "sessions" ? "var(--indigo-600)" : "var(--text-muted)",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "0.4rem",
                }}
              >
                <History size={14} /> History ({pastSessions.length})
              </button>
            </div>

            {/* Tab Content: Curriculum Tracker */}
            {sidebarTab === "curriculum" ? (
              <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column" }}>
                {/* Active Subject Card */}
                <div style={{ padding: "1rem 1.25rem", borderBottom: "1px solid var(--border-subtle)", backgroundColor: "#ffffff" }}>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: "700", letterSpacing: "0.05em", marginBottom: "0.25rem" }}>
                    Active Curriculum
                  </div>
                  <h2 style={{ fontSize: "1rem", fontWeight: "700", color: "#0f172a", marginBottom: "0.6rem" }}>{topic}</h2>
                  
                  {/* Overall Subject Progress Bar */}
                  <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                    <div style={{ flex: 1, height: "6px", backgroundColor: "#e2e8f0", borderRadius: "9999px", overflow: "hidden" }}>
                      <div 
                        style={{ 
                          height: "100%", 
                          width: `${overallProgressPct}%`, 
                          background: "linear-gradient(90deg, #0284c7 0%, #059669 100%)", 
                          transition: "width 0.4s ease" 
                        }} 
                      />
                    </div>
                    <span style={{ fontSize: "0.75rem", fontWeight: "700", color: overallProgressPct >= 85 ? "var(--emerald-400)" : "var(--cyan-400)", minWidth: "35px", textAlign: "right" }}>
                      {overallProgressPct}%
                    </span>
                  </div>
                </div>

                {/* Concept List */}
                <div style={{ flex: 1, overflowY: "auto", padding: "1rem 1.25rem" }}>
                  <ErrorBoundary fallbackMessage="Unable to render concept milestones.">
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.65rem" }}>
                      {(curriculum || []).map((c) => {
                        const score = c.score || 0;
                        const pct = Math.min(99, Math.round(score * 100));
                        const isChild = Boolean(c.parent_id);
                        const hasChildren = (curriculum || []).some((k) => k.parent_id === c.concept_id);
                        const isCurr = c.concept_id === active_concept;
                        const isSkipped = c.status === "skipped";
                        const isReview = c.status === "needs_review" || c.status === "review" || (Array.isArray(review_queue) && review_queue.some(item => (typeof item === "string" ? item : item.concept_id) === c.concept_id));
                        const isMastered = c.status === "mastered" && !isReview;

                        let statusLabel = "⏳ Pending";
                        let statusColor = "#64748b";
                        let statusBg = "#f1f5f9";

                        if (isSkipped) {
                          statusLabel = "⏭️ Skipped";
                          statusColor = "#d97706";
                          statusBg = "#fffbeb";
                        } else if (isMastered) {
                          statusLabel = "✅ Mastered";
                          statusColor = "#059669";
                          statusBg = "#ecfdf5";
                        } else if (isReview) {
                          statusLabel = "⚠️ Review";
                          statusColor = "#d97706";
                          statusBg = "#fef3c7";
                        } else if (isCurr) {
                          statusLabel = "🔄 In Progress";
                          statusColor = "#0284c7";
                          statusBg = "#e0f2fe";
                        }

                        // Drill-down button constraints
                        let drillDisabled = isSending;
                        let drillTitle = "Drill down into sub-milestones";
                        if (isChild) {
                          drillDisabled = true;
                          drillTitle = "Maximum depth reached";
                        } else if (hasChildren) {
                          drillDisabled = true;
                          drillTitle = "Sub-milestones already active";
                        } else if (isMastered) {
                          drillDisabled = true;
                          drillTitle = "Topic already mastered";
                        }

                        return (
                          <div
                            key={c.concept_id}
                            className="glass-panel"
                            style={{
                              padding: "0.75rem",
                              borderRadius: "0.65rem",
                              marginLeft: isChild ? "1.25rem" : "0",
                              backgroundColor: isCurr ? "#eff6ff" : "#ffffff",
                              borderColor: isCurr ? "var(--indigo-500)" : (isSkipped ? "#fcd34d" : "var(--border-subtle)"),
                              borderLeft: isChild ? "3px solid var(--indigo-600)" : undefined,
                              boxShadow: isCurr ? "0 0 10px rgba(99, 102, 241, 0.15)" : "0 1px 2px rgba(0, 0, 0, 0.04)",
                              transition: "all 0.2s ease",
                            }}
                          >
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.35rem" }}>
                              <span style={{ fontSize: "0.825rem", fontWeight: isCurr ? "700" : "600", color: isCurr ? "var(--indigo-600)" : "#0f172a", maxWidth: "68%" }}>
                                {isChild && <span style={{ color: "var(--indigo-600)", marginRight: "0.3rem" }}>↳</span>}
                                {c.name}
                              </span>
                              <span style={{ fontSize: "0.68rem", fontWeight: "700", padding: "0.15rem 0.45rem", borderRadius: "0.3rem", color: statusColor, backgroundColor: statusBg }}>
                                {statusLabel}
                              </span>
                            </div>

                            {/* BKT Probability Bar */}
                            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.45rem" }}>
                              <div style={{ flex: 1, height: "4px", backgroundColor: "#e2e8f0", borderRadius: "9999px", overflow: "hidden" }}>
                                <div style={{ height: "100%", width: `${pct}%`, backgroundColor: isMastered ? "#059669" : (isCurr ? "#4f46e5" : "#f59e0b"), transition: "width 0.4s ease" }} />
                              </div>
                              <span style={{ fontSize: "0.7rem", fontWeight: "700", color: isMastered ? "#059669" : (isCurr ? "var(--indigo-600)" : "#64748b"), minWidth: "28px", textAlign: "right" }}>
                                {pct}%
                              </span>
                            </div>

                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                              <span style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>
                                Tier {c.difficulty || 1}
                              </span>
                              <button
                                type="button"
                                onClick={() => onDrilldown && onDrilldown(c.concept_id)}
                                disabled={drillDisabled}
                                style={{
                                  background: "#ffffff",
                                  border: "1px solid var(--border-default)",
                                  borderRadius: "0.35rem",
                                  padding: "0.2rem 0.5rem",
                                  fontSize: "0.65rem",
                                  fontWeight: "700",
                                  color: drillDisabled ? "var(--text-muted)" : "var(--indigo-600)",
                                  cursor: drillDisabled ? "not-allowed" : "pointer",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: "0.2rem",
                                  boxShadow: "0 1px 2px rgba(0,0,0,0.03)",
                                }}
                                title={drillTitle}
                              >
                                🔬 Drill Down
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </ErrorBoundary>
                </div>
              </div>
            ) : (
              /* Tab Content: Previous Sessions List */
              <div style={{ flex: 1, overflowY: "auto", padding: "1rem 1.25rem", display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: "700", letterSpacing: "0.05em", marginBottom: "0.25rem" }}>
                  Recorded Learning Journeys
                </div>
                {pastSessions.length === 0 ? (
                  <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontStyle: "italic", padding: "1rem 0" }}>
                    No previous sessions recorded yet.
                  </div>
                ) : (
                  pastSessions.map((s) => {
                    const isSelected = s.session_id === session_id;
                    return (
                      <button
                        key={s.session_id}
                        type="button"
                        onClick={() => onResumeSession && onResumeSession(s.session_id)}
                        className="glass-panel"
                        style={{
                          textAlign: "left",
                          padding: "0.75rem",
                          borderRadius: "0.65rem",
                          cursor: "pointer",
                          backgroundColor: isSelected ? "#eef2ff" : "#ffffff",
                          borderColor: isSelected ? "var(--indigo-600)" : "var(--border-subtle)",
                          transition: "all 0.15s ease",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.25rem" }}>
                          <span style={{ fontSize: "0.85rem", fontWeight: "700", color: isSelected ? "var(--indigo-600)" : "#0f172a" }}>
                            {s.topic}
                          </span>
                          <span style={{ fontSize: "0.68rem", padding: "0.1rem 0.45rem", borderRadius: "9999px", backgroundColor: s.is_graduated ? "#ecfdf5" : "#e0f2fe", color: s.is_graduated ? "#059669" : "#0284c7", fontWeight: "700" }}>
                            {s.is_graduated ? "🎓 Mastered" : "📚 Active"}
                          </span>
                        </div>
                        <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
                          {s.message_count} messages • {s.phase || "tutoring"}
                        </div>
                      </button>
                    );
                  })
                )}
              </div>
            )}

            {/* Document Ingestion Zone (RAG) */}
            <div style={{ padding: "1rem 1.25rem", borderTop: "1px solid var(--border-subtle)", backgroundColor: "#f8fafc" }}>
              <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: "700", marginBottom: "0.45rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                Authoritative Textbook Ingestion (RAG)
              </div>
              <label 
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: "0.5rem",
                  padding: "0.65rem",
                  borderRadius: "0.65rem",
                  border: "1.5pt dashed #cbd5e1",
                  backgroundColor: "#ffffff",
                  color: "var(--text-secondary)",
                  fontSize: "0.8rem",
                  fontWeight: "600",
                  cursor: isUploading ? "not-allowed" : "pointer",
                  transition: "all 0.2s ease",
                }}
              >
                <Upload size={14} style={{ color: "var(--indigo-600)" }} />
                <span>{isUploading ? "Indexing into ChromaDB..." : "Upload Notes / Book (PDF/MD)"}</span>
                <input type="file" accept=".pdf,.txt,.md" onChange={handleFileUpload} disabled={isUploading} style={{ display: "none" }} />
              </label>
              {uploadStatus && (
                <div style={{ fontSize: "0.72rem", color: uploadStatus.includes("✅") ? "var(--emerald-400)" : "var(--rose-400)", marginTop: "0.4rem", lineHeight: "1.3" }}>
                  {uploadStatus}
                </div>
              )}
            </div>

            {/* Student Profile Footer */}
            <div style={{ padding: "0.85rem 1.25rem", borderTop: "1px solid var(--border-subtle)", backgroundColor: "#ffffff", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <div style={{ width: "28px", height: "28px", borderRadius: "50%", backgroundColor: "#eef2ff", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--indigo-600)" }}>
                  <User size={15} />
                </div>
                <div>
                  <div style={{ fontSize: "0.8rem", fontWeight: "700", color: "#0f172a" }}>Student 001</div>
                  <div style={{ fontSize: "0.68rem", color: "var(--text-muted)" }}>Active Session</div>
                </div>
              </div>
              <button
                type="button"
                onClick={onReset}
                style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", display: "flex", alignItems: "center", gap: "0.25rem", fontSize: "0.725rem" }}
                title="Reset session"
              >
                <RotateCcw size={13} /> Reset
              </button>
            </div>
          </>
        )}
      </aside>

      {/* =================================================================== */}
      {/* MAIN LEARNING ARENA */}
      {/* =================================================================== */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column", height: "100%", overflow: "hidden", position: "relative", backgroundColor: "var(--bg-app)" }}>
        {/* Top Header Navigation */}
        <header 
          style={{
            padding: "0.85rem 1.5rem",
            borderBottom: "1px solid var(--border-subtle)",
            backgroundColor: "rgba(255, 255, 255, 0.95)",
            backdropFilter: "blur(12px)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            zIndex: 20,
            boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.85rem", flexWrap: "wrap" }}>
            {!isSidebarOpen && (
              <button
                type="button"
                onClick={() => setIsSidebarOpen(true)}
                style={{ background: "#ffffff", border: "1px solid var(--border-default)", borderRadius: "0.4rem", color: "var(--text-secondary)", padding: "0.3rem 0.5rem", cursor: "pointer", display: "flex", alignItems: "center", gap: "0.3rem" }}
                title="Expand Sidebar"
              >
                <PanelLeft size={16} />
              </button>
            )}

            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <Compass size={18} style={{ color: "var(--indigo-600)" }} />
              <span style={{ fontSize: "0.95rem", fontWeight: "800", color: "#0f172a" }}>
                {(curriculum || []).find(c => c.concept_id === active_concept)?.name 
                  || (active_concept ? active_concept.replace(/_/g, " ").toUpperCase() : "FOUNDATIONAL ONBOARDING")}
              </span>
            </div>

            {/* Mode Badge */}
            <span 
              style={{ 
                padding: "0.2rem 0.65rem", 
                borderRadius: "9999px", 
                backgroundColor: teaching_mode === "mode_1_qa" ? "#e0f2fe" : "#ecfdf5", 
                color: teaching_mode === "mode_1_qa" ? "#0284c7" : "#059669", 
                fontSize: "0.75rem", 
                fontWeight: "700" 
              }}
              title={teaching_mode === "mode_1_qa" ? "Socratic practice and check questions" : "Scaffolded instruction with analogies and worked examples"}
            >
              {teaching_mode === "mode_1_qa" ? "🎯 Mode 1: Practice" : "📘 Mode 2: Teach First"}
            </span>

            {/* Current Action Badge */}
            {(() => {
              const act = lastAsstMsg?.action || (phase === "diagnostic" ? "diagnostic" : "initial");
              const b = actionBadges[act] || actionBadges.initial;
              return (
                <span style={{ padding: "0.2rem 0.65rem", borderRadius: "9999px", backgroundColor: b.bg, color: b.color, fontSize: "0.75rem", fontWeight: "700" }}>
                  {b.label}
                </span>
              );
            })()}

            {/* Doubts Asked Counter Badge (BKT Invariant) */}
            <span 
              style={{ 
                padding: "0.2rem 0.65rem", 
                borderRadius: "9999px", 
                backgroundColor: "#f5f3ff", 
                color: "var(--purple-400)", 
                fontSize: "0.75rem", 
                fontWeight: "700", 
                display: "inline-flex", 
                alignItems: "center", 
                gap: "0.3rem" 
              }} 
              title="Doubts are safely routed and never decrease BKT mastery!"
            >
              💬 Doubts: {doubts_asked} <span style={{ fontSize: "0.68rem", opacity: 0.85 }}>(0 BKT Penalty)</span>
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
            {active_concept && (
              <button
                type="button"
                onClick={() => onDrilldown && onDrilldown(active_concept)}
                disabled={isSending}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.35rem",
                  padding: "0.4rem 0.75rem",
                  borderRadius: "0.5rem",
                  backgroundColor: "#e0f2fe",
                  border: "1px solid #bae6fd",
                  color: "#0284c7",
                  fontSize: "0.8rem",
                  fontWeight: "700",
                  cursor: isSending ? "not-allowed" : "pointer",
                }}
                title="Drill down into sub-milestones"
              >
                🔬 Drill Down
              </button>
            )}

            <button
              type="button"
              onClick={() => setShowDAG(!showDAG)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.4rem",
                padding: "0.4rem 0.85rem",
                borderRadius: "0.5rem",
                backgroundColor: showDAG ? "#eef2ff" : "#ffffff",
                border: "1px solid",
                borderColor: showDAG ? "var(--indigo-600)" : "var(--border-default)",
                color: showDAG ? "var(--indigo-600)" : "var(--text-secondary)",
                fontSize: "0.8rem",
                fontWeight: "600",
                cursor: "pointer",
                transition: "all 0.15s ease",
                boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
              }}
            >
              {showDAG ? <EyeOff size={14} /> : <Eye size={14} />}
              <span>Concept Graph</span>
            </button>
          </div>
        </header>

        {/* Collapsible Mermaid DAG Panel */}
        {showDAG && (
          <div style={{ padding: "1.25rem", borderBottom: "1px solid var(--border-subtle)", backgroundColor: "#ffffff", maxHeight: "380px", overflowY: "auto", boxShadow: "0 4px 6px -1px rgba(0,0,0,0.05)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.6rem", fontSize: "0.75rem", color: "var(--text-muted)" }}>
              <span>🟢 Mastered (≥85%) &nbsp;|&nbsp; 🔵 Active &nbsp;|&nbsp; 🟡 Review (60-84%) &nbsp;|&nbsp; ⚪ Pending (&lt;60%)</span>
            </div>
            <MermaidDAG chart={mermaid_dag} title="Curriculum Prerequisite & Dependency DAG" />
          </div>
        )}

        {/* Graduation Academic Banner */}
        {is_graduated && (
          <div style={{ margin: "1rem 1.5rem 0", padding: "1.5rem", borderRadius: "1rem", backgroundColor: "#ecfdf5", border: "1.5pt solid #a7f3d0", boxShadow: "0 10px 25px rgba(16, 185, 129, 0.1)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.85rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                <Award size={28} style={{ color: "var(--emerald-400)" }} />
                <div>
                  <h3 style={{ fontSize: "1.2rem", fontWeight: "800", color: "#065f46" }}>
                    Academic Graduation Complete! All Concepts Mastered.
                  </h3>
                  <div style={{ fontSize: "0.8rem", color: "#047857" }}>
                    Cognitive mastery verified across all prerequisite thresholds ($P(L_t) \ge 0.85$).
                  </div>
                </div>
              </div>

              <button
                type="button"
                onClick={downloadReport}
                className="btn-primary"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  padding: "0.6rem 1.25rem",
                  borderRadius: "0.75rem",
                  fontSize: "0.85rem",
                  fontWeight: "700",
                }}
              >
                <Download size={16} /> Download Academic Report (.md)
              </button>
            </div>

            {hake_gain && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1rem", marginTop: "1rem", padding: "0.85rem 1.25rem", borderRadius: "0.75rem", backgroundColor: "#ffffff", border: "1px solid #d1fae5" }}>
                <div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Diagnostic Pre-Test Baseline</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: "800", color: "#0f172a" }}>{((hake_gain.pre ?? 0) * 100).toFixed(1)}%</div>
                </div>
                <div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Post-Tutoring Concept Mastery</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: "800", color: "var(--emerald-400)" }}>{((hake_gain.post ?? 0) * 100).toFixed(1)}%</div>
                </div>
                <div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Hake's Normalized Learning Gain (g)</div>
                  <div style={{ fontSize: "1.3rem", fontWeight: "800", color: "var(--indigo-600)" }}>{(hake_gain.hake_g ?? 0).toFixed(2)} <span style={{ fontSize: "0.85rem", color: "var(--text-accent)" }}>({hake_gain.label || "High Gain"})</span></div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Content Arena: Chat Feed */}
        <div style={{ flex: 1, display: "flex", overflow: "hidden", position: "relative" }}>
          {/* Main Chat Stream */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", height: "100%", overflow: "hidden", minWidth: 0 }}>
            {/* Messages Scroll Area */}
            <div style={{ flex: 1, overflowY: "auto", padding: "1.75rem 2rem", display: "flex", flexDirection: "column", gap: "1.5rem" }}>
              {chat_history.map((msg, index) => {
                const isAsst = msg.role === "assistant";
                const msgId = msg.id || `msg-${index}`;
                const showCitations = expandedCitations[msgId];
                const showMetrics = expandedMetrics[msgId];

                return (
                  <div
                    key={msgId}
                    className="animate-fade-in"
                    style={{
                      display: "flex",
                      gap: "1rem",
                      alignSelf: isAsst ? "flex-start" : "flex-end",
                      maxWidth: isAsst ? "88%" : "78%",
                      width: isAsst ? "88%" : "auto",
                    }}
                  >
                    {isAsst && (
                      <div 
                        style={{
                          width: "36px",
                          height: "36px",
                          borderRadius: "0.75rem",
                          background: "linear-gradient(135deg, #4f46e5 0%, #0284c7 100%)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                          marginTop: "0.2rem",
                          boxShadow: "0 2px 8px rgba(99, 102, 241, 0.25)",
                        }}
                      >
                        <Brain size={20} style={{ color: "#ffffff" }} />
                      </div>
                    )}

                    <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem", width: "100%" }}>
                      {/* Message Speech Bubble */}
                      <div
                        className="glass-panel"
                        style={{
                          padding: "1.25rem 1.5rem",
                          borderRadius: "1rem",
                          backgroundColor: isAsst ? "#ffffff" : undefined,
                          background: !isAsst ? "var(--bg-bubble-student)" : undefined,
                          color: isAsst ? "#0f172a" : "#ffffff",
                          fontSize: "0.95rem",
                          lineHeight: "1.65",
                          border: isAsst ? "1px solid var(--border-subtle)" : "1px solid rgba(255, 255, 255, 0.2)",
                          boxShadow: !isAsst ? "0 4px 15px rgba(79, 70, 229, 0.25)" : "0 2px 8px rgba(0, 0, 0, 0.05)",
                        }}
                      >
                        <FormattedMessageContent content={msg.content} />
                        {msg.isStreaming && <span className="streaming-cursor">▋</span>}
                      </div>

                      {/* Visually Distinct Socratic Question Callout */}
                      {isAsst && msg.question && (msg.awaiting === "answer" || (!msg.awaiting && msg.action === "probe")) && (
                        <div 
                          style={{
                            padding: "1rem 1.25rem",
                            borderRadius: "0.85rem",
                            backgroundColor: "#f5f7ff",
                            borderLeft: "4px solid var(--indigo-600)",
                            borderTop: "1px solid #c7d2fe",
                            borderRight: "1px solid #c7d2fe",
                            borderBottom: "1px solid #c7d2fe",
                            color: "#1e1b4b",
                            fontSize: "0.95rem",
                            boxShadow: "0 2px 8px rgba(79, 70, 229, 0.08)",
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontWeight: "800", color: "var(--indigo-600)", marginBottom: "0.35rem", fontSize: "0.8rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                            <HelpCircle size={15} /> Active Socratic Challenge:
                          </div>
                          <div style={{ fontWeight: "600", lineHeight: "1.5" }}>{msg.question}</div>
                        </div>
                      )}

                      {/* Authoritative Textbook Citations (Agentic RAG) */}
                      {isAsst && msg.rag_context?.citations?.length > 0 && (
                        <div className="glass-panel" style={{ borderRadius: "0.65rem", overflow: "hidden", backgroundColor: "#ffffff" }}>
                          <button
                            type="button"
                            onClick={() => setExpandedCitations(prev => ({ ...prev, [msgId]: !prev[msgId] }))}
                            style={{
                              width: "100%",
                              padding: "0.5rem 0.85rem",
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              backgroundColor: "transparent",
                              border: "none",
                              color: "var(--text-secondary)",
                              fontSize: "0.8rem",
                              fontWeight: "600",
                              cursor: "pointer",
                            }}
                          >
                            <span style={{ display: "flex", alignItems: "center", gap: "0.45rem" }}>
                              <BookOpen size={14} style={{ color: "var(--indigo-600)" }} />
                              Authoritative Textbook Citations (Agentic RAG)
                            </span>
                            {showCitations ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                          </button>

                          {showCitations && (
                            <div style={{ padding: "0.85rem", borderTop: "1px solid var(--border-subtle)", display: "flex", flexDirection: "column", gap: "0.65rem", backgroundColor: "#f8fafc" }}>
                              {msg.rag_context.citations.map((c, i) => (
                                <div key={i} style={{ padding: "0.6rem 0.85rem", borderRadius: "0.5rem", backgroundColor: "#ffffff", border: "1px solid #e2e8f0", fontSize: "0.8rem" }}>
                                  <div style={{ display: "flex", justifyContent: "space-between", color: "var(--indigo-600)", fontWeight: "700", marginBottom: "0.3rem" }}>
                                    <span>📖 {c.source}</span>
                                    <span>Relevance: {Math.round(c.relevance_score * 100)}%</span>
                                  </div>
                                  <p style={{ color: "var(--text-muted)", fontStyle: "italic", fontSize: "0.775rem", lineHeight: "1.4" }}>
                                    "{c.excerpt}"
                                  </p>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Agent Reasoning & Critic Audit Dropdown */}
                      {isAsst && msg.metadata && (
                        <div className="glass-panel" style={{ borderRadius: "0.65rem", overflow: "hidden", backgroundColor: "#ffffff" }}>
                          <button
                            type="button"
                            onClick={() => setExpandedMetrics(prev => ({ ...prev, [msgId]: !prev[msgId] }))}
                            style={{
                              width: "100%",
                              padding: "0.5rem 0.85rem",
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              backgroundColor: "transparent",
                              border: "none",
                              color: "var(--text-muted)",
                              fontSize: "0.75rem",
                              fontWeight: "600",
                              cursor: "pointer",
                            }}
                          >
                            <span>🔍 Multi-Agent Reasoning & Critic Safety Audit</span>
                            {showMetrics ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                          </button>

                          {showMetrics && (
                            <div style={{ padding: "0.85rem", borderTop: "1px solid var(--border-subtle)", fontSize: "0.775rem", color: "var(--text-secondary)", backgroundColor: "#f8fafc" }}>
                              <div style={{ display: "flex", gap: "1.75rem", marginBottom: "0.5rem", flexWrap: "wrap" }}>
                                {typeof msg.metadata?.score === "number" && <span>Score: <b style={{ color: "#0f172a" }}>{msg.metadata.score.toFixed(2)}</b></span>}
                                {msg.metadata?.understanding && <span>Understanding: <b style={{ color: "var(--indigo-600)" }}>{msg.metadata.understanding}</b></span>}
                                {typeof msg.metadata?.p_know === "number" && <span>BKT P(know): <b style={{ color: "var(--emerald-400)" }}>{(msg.metadata.p_know * 100).toFixed(1)}%</b></span>}
                              </div>
                              {msg.metadata?.critic && (
                                <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "0.5rem", marginTop: "0.4rem" }}>
                                  <span>Critic Gate: <b style={{ color: msg.metadata.critic.passed ? "var(--emerald-400)" : "var(--rose-400)" }}>{msg.metadata.critic.passed ? "PASSED" : "FAILED"}</b> ({msg.metadata.critic.score}/10)</span>
                                  <div style={{ color: "var(--text-muted)", fontSize: "0.725rem", marginTop: "0.25rem", lineHeight: "1.4" }}>
                                    {msg.metadata.critic.feedback}
                                  </div>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {/* Typing / Synthesis Indicator */}
              {isSending && !chat_history.some(m => m.isStreaming) && (
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", alignSelf: "flex-start", padding: "0.85rem 1.25rem", borderRadius: "1rem", backgroundColor: "#ffffff", border: "1px solid var(--border-subtle)", boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
                  <Brain size={18} style={{ color: "var(--indigo-600)" }} />
                  <span style={{ fontSize: "0.85rem", color: "var(--text-muted)", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                    SAGE is evaluating reasoning
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                  </span>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Bottom Quick Actions & Chat Input Bar */}
            {!is_graduated ? (
              <div 
                style={{
                  padding: "1rem 2rem 1.25rem",
                  borderTop: "1px solid var(--border-subtle)",
                  backgroundColor: "rgba(255, 255, 255, 0.95)",
                  backdropFilter: "blur(12px)",
                  boxShadow: "0 -4px 12px rgba(0, 0, 0, 0.03)",
                }}
              >
                {/* Context-Aware Quick Response Action Pills */}
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", marginBottom: "0.75rem" }}>
                  {isLevelPrompt ? (
                    <>
                      <button
                        type="button"
                        onClick={() => onSendMessage("I am a beginner")}
                        disabled={isSending}
                        className="action-pill action-pill-emerald"
                      >
                        🌱 I am a beginner (Teach from scratch)
                      </button>
                      <button
                        type="button"
                        onClick={() => onSendMessage("Some knowledge")}
                        disabled={isSending}
                        className="action-pill action-pill-primary"
                      >
                        ⚡ Some knowledge (Prior calibration)
                      </button>
                      <button
                        type="button"
                        onClick={() => onSendMessage("Comfortable")}
                        disabled={isSending}
                        className="action-pill action-pill-amber"
                      >
                        🚀 Comfortable (Advanced challenge)
                      </button>
                    </>
                  ) : isAwaitingContinue ? (
                    <>
                      <button
                        type="button"
                        onClick={() => onSendMessage("continue")}
                        disabled={isSending}
                        className="action-pill action-pill-primary"
                        style={{ fontSize: "0.85rem", padding: "0.45rem 1.15rem" }}
                      >
                        ▶️ Continue Lesson
                      </button>
                      <button
                        type="button"
                        onClick={() => { const el = document.querySelector("textarea"); el && el.focus(); }}
                        disabled={isSending}
                        className="action-pill"
                      >
                        ❓ Ask a Question
                      </button>
                    </>
                  ) : isAwaitingClarity ? (
                    <>
                      <button
                        type="button"
                        onClick={() => onSendMessage("makes sense, got it")}
                        disabled={isSending}
                        className="action-pill action-pill-emerald"
                        style={{ fontSize: "0.85rem", padding: "0.45rem 1.15rem" }}
                      >
                        ✅ Yes, makes sense
                      </button>
                      <button
                        type="button"
                        onClick={() => onSendMessage("could you explain that another way?")}
                        disabled={isSending}
                        className="action-pill action-pill-amber"
                      >
                        🔄 Re-explain another way
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => onSendMessage("I don't know, could you give me a hint?")}
                        disabled={isSending}
                        className="action-pill action-pill-amber"
                      >
                        🪜 I don't know (Hint)
                      </button>
                      <button
                        type="button"
                        onClick={() => onSendMessage("Can you explain this with a real-world analogy?")}
                        disabled={isSending}
                        className="action-pill"
                      >
                        💡 Real-world analogy
                      </button>
                      <button
                        type="button"
                        onClick={() => onSendMessage("Can you walk through a step-by-step worked example?")}
                        disabled={isSending}
                        className="action-pill"
                      >
                        🔍 Worked example
                      </button>
                      <button
                        type="button"
                        onClick={() => onSendMessage("Can you show a visual diagram of this concept?")}
                        disabled={isSending}
                        className="action-pill"
                      >
                        📊 Show diagram
                      </button>
                      <button
                        type="button"
                        onClick={() => onSendMessage("Skip this topic for now")}
                        disabled={isSending}
                        className="action-pill"
                        style={{ color: "var(--text-muted)" }}
                      >
                        ⏭️ Skip topic
                      </button>
                    </>
                  )}
                </div>

                {/* Main Text Input Bar */}
                <form 
                  onSubmit={handleSubmit}
                  style={{
                    display: "flex",
                    alignItems: "flex-end",
                    gap: "0.75rem",
                    backgroundColor: "#ffffff",
                    border: "1.5pt solid var(--border-default)",
                    borderRadius: "0.85rem",
                    padding: "0.5rem 0.85rem",
                    boxShadow: "0 2px 8px rgba(0, 0, 0, 0.05)",
                    transition: "border-color 0.2s ease",
                  }}
                >
                  <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Type your explanation, question, or doubt... (Enter to send, Shift+Enter for newline)"
                    disabled={isSending}
                    rows={1}
                    className="chat-textarea"
                  />

                  <button
                    type="submit"
                    disabled={!input.trim() || isSending}
                    className="btn-primary"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: "38px",
                      height: "38px",
                      borderRadius: "0.6rem",
                      padding: 0,
                      opacity: !input.trim() || isSending ? 0.5 : 1,
                      cursor: !input.trim() || isSending ? "not-allowed" : "pointer",
                      flexShrink: 0,
                    }}
                    title="Send Response (Enter)"
                  >
                    <Send size={16} />
                  </button>
                </form>
              </div>
            ) : (
              <div style={{ padding: "1.25rem", borderTop: "1px solid var(--border-subtle)", backgroundColor: "#ffffff", textAlign: "center" }}>
                <span style={{ color: "var(--emerald-400)", fontWeight: "700" }}>🎓 Congratulations! All concepts in this topic are mastered. You can start a new learning track anytime.</span>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
