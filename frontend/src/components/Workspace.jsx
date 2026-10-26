import React, { useState, useRef, useEffect } from "react";
import { 
  Send, Brain, BookOpen, ChevronDown, ChevronUp, Upload, 
  RotateCcw, Sparkles, CheckCircle2, Award, Download, 
  Code, Eye, EyeOff, Layers, HelpCircle, MessageSquare, FastForward
} from "lucide-react";
import confetti from "canvas-confetti";
import MermaidDAG from "./MermaidDAG";
import InteractiveStudio from "./InteractiveStudio";
import ErrorBoundary from "./ErrorBoundary";
import { marked } from "marked";

marked.setOptions({
  gfm: true,
  breaks: true,
});

/**
 * Parses message content for Mermaid diagrams and markdown formatted text blocks.
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
    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
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

export default function Workspace({ sessionData, onSendMessage, onUploadDoc, onDrilldown, onReset, isSending }) {
  const [input, setInput] = useState("");
  const [showDAG, setShowDAG] = useState(false);
  const [showStudio, setShowStudio] = useState(false);
  const [expandedCitations, setExpandedCitations] = useState({});
  const [expandedMetrics, setExpandedMetrics] = useState({});
  const [uploadStatus, setUploadStatus] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const messagesEndRef = useRef(null);

  const { 
    session_id, topic, chat_history, curriculum, 
    mermaid_dag, mastery, active_concept, phase, is_graduated, hake_gain,
    teaching_mode = "mode_2_teach_first", doubts_asked = 0, visuals = [], review_queue = []
  } = sessionData;

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat_history]);

  // Trigger confetti upon graduation
  useEffect(() => {
    if (is_graduated) {
      confetti({
        particleCount: 120,
        spread: 70,
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
    setUploadStatus("Uploading & embedding document into ChromaDB...");
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
    initial: { label: "🌱 Initial Inquiry", color: "#10b981", bg: "rgba(16, 185, 129, 0.15)" },
    probe: { label: "🔍 Socratic Probe", color: "#38bdf8", bg: "rgba(56, 189, 248, 0.15)" },
    hint: { label: "💡 Guided Hint", color: "#facc15", bg: "rgba(250, 204, 21, 0.15)" },
    scaffold: { label: "🪜 Reasoning Scaffold", color: "#fb923c", bg: "rgba(251, 146, 60, 0.15)" },
    explain: { label: "📖 Concept Scaffold", color: "#c084fc", bg: "rgba(192, 132, 252, 0.15)" },
    advance: { label: "🚀 Concept Advance", color: "#34d399", bg: "rgba(52, 211, 153, 0.15)" },
    diagnostic: { label: "📋 Diagnostic Assessment", color: "#60a5fa", bg: "rgba(96, 165, 250, 0.15)" },
  };

  // Inspect the latest assistant message to determine if an onboarding level prompt is pending
  const lastAsstMsg = [...chat_history].reverse().find(m => m.role === "assistant");
  const lastMsgText = (lastAsstMsg?.content || "").toLowerCase();
  const isLevelPrompt = lastMsgText.includes("beginner") && (lastMsgText.includes("comfortable") || lastMsgText.includes("experience"));
  const isAwaitingContinue = lastAsstMsg?.awaiting === "continue" || (!lastAsstMsg?.question && (lastMsgText.includes("click continue") || lastMsgText.includes("click **continue**")));
  const isAwaitingClarity = lastAsstMsg?.awaiting === "clarity_check" || lastMsgText.includes("does that make sense");

  return (
    <div style={{ display: "flex", height: "100vh", width: "100vw", backgroundColor: "#0b0f19", color: "#f8fafc", overflow: "hidden" }}>
      {/* =================================================================== */}
      {/* SIDEBAR */}
      {/* =================================================================== */}
      <div style={{ width: "350px", backgroundColor: "#0f172a", borderRight: "1px solid #1e293b", display: "flex", flexDirection: "column", flexShrink: 0 }}>
        {/* Brand Header */}
        <div style={{ padding: "1.25rem", borderBottom: "1px solid #1e293b", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <Brain size={24} style={{ color: "#38bdf8" }} />
            <span style={{ fontWeight: "800", fontSize: "1.25rem", letterSpacing: "-0.02em" }}>SAGE</span>
          </div>
          <button
            onClick={onReset}
            style={{ display: "flex", alignItems: "center", gap: "0.3rem", padding: "0.35rem 0.65rem", borderRadius: "0.375rem", backgroundColor: "#1e293b", border: "1px solid #334155", color: "#94a3b8", fontSize: "0.75rem", cursor: "pointer" }}
            title="Switch Topic"
          >
            <RotateCcw size={13} /> Change Topic
          </button>
        </div>

        {/* Topic Title & Phase */}
        <div style={{ padding: "1.1rem 1.25rem", borderBottom: "1px solid #1e293b", backgroundColor: "rgba(15, 23, 42, 0.6)" }}>
          <div style={{ fontSize: "0.7rem", color: "#64748b", textTransform: "uppercase", fontWeight: "700", letterSpacing: "0.05em", marginBottom: "0.25rem" }}>
            Subject / Curriculum Track
          </div>
          <h2 style={{ fontSize: "1.05rem", fontWeight: "700", color: "#f1f5f9", marginBottom: "0.5rem" }}>{topic}</h2>
          
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem", padding: "0.2rem 0.55rem", borderRadius: "9999px", backgroundColor: phase === "graduated" ? "rgba(16, 185, 129, 0.2)" : (phase === "diagnostic" ? "rgba(59, 130, 246, 0.2)" : "rgba(168, 85, 247, 0.2)"), color: phase === "graduated" ? "#34d399" : (phase === "diagnostic" ? "#60a5fa" : "#c084fc"), fontSize: "0.725rem", fontWeight: "700" }}>
              {phase === "graduated" ? "🎓 Mastered & Graduated" : (phase === "diagnostic" ? "📋 Diagnostic Assessment" : "📚 Tutoring Active")}
            </span>
          </div>
        </div>

        {/* BKT Knowledge Meters & Progress Tracker */}
        <div style={{ flex: 1, overflowY: "auto", padding: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.85rem" }}>
            <div style={{ fontSize: "0.75rem", color: "#64748b", textTransform: "uppercase", fontWeight: "700", letterSpacing: "0.05em" }}>
              Topic Progress Tracker
            </div>
            <span style={{ fontSize: "0.7rem", color: "#94a3b8" }}>
              {(curriculum || []).filter(c => c.status === "mastered" || (c.score || 0) >= 0.85).length}/{(curriculum || []).length} done
            </span>
          </div>

          <ErrorBoundary fallbackMessage="Unable to render topic progress tracker.">
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              {(curriculum || []).map((c) => {
                const score = c.score || 0;
                // Clamp P(L) in UI display: never show 100%
                const pct = Math.min(99, Math.round(score * 100));
                const isChild = Boolean(c.parent_id);
                const hasChildren = (curriculum || []).some((k) => k.parent_id === c.concept_id);
                const isCurr = c.concept_id === active_concept;
                const isSkipped = c.status === "skipped";
                const isReview = c.status === "needs_review" || c.status === "review" || (Array.isArray(review_queue) && review_queue.some(item => (typeof item === "string" ? item : item.concept_id) === c.concept_id));
                const isMastered = c.status === "mastered" && !isReview;

                let statusLabel = "⏳ Pending";
                let statusColor = "#64748b";
                let statusBg = "rgba(100, 116, 139, 0.15)";

                if (isSkipped) {
                  statusLabel = "⏭️ Skipped";
                  statusColor = "#f59e0b";
                  statusBg = "rgba(245, 158, 11, 0.15)";
                } else if (isMastered) {
                  statusLabel = "✅ Mastered";
                  statusColor = "#10b981";
                  statusBg = "rgba(16, 185, 129, 0.15)";
                } else if (isReview) {
                  statusLabel = "⚠️ Needs review";
                  statusColor = "#eab308";
                  statusBg = "rgba(234, 179, 8, 0.15)";
                } else if (isCurr) {
                  statusLabel = "🔄 In Progress";
                  statusColor = "#38bdf8";
                  statusBg = "rgba(56, 189, 248, 0.15)";
                }

                // Drill-down eligibility
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
                    style={{
                      padding: "0.75rem",
                      borderRadius: "0.5rem",
                      marginLeft: isChild ? "1.25rem" : "0",
                      backgroundColor: isCurr ? "#1e293b" : "rgba(30, 41, 59, 0.4)",
                      border: isCurr ? "1px solid #38bdf8" : (isSkipped ? "1px solid #b45309" : "1px solid #1e293b"),
                      borderLeft: isChild ? "3px solid #0284c7" : undefined,
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.35rem" }}>
                      <span style={{ fontSize: "0.825rem", fontWeight: isCurr ? "700" : "500", color: isCurr ? "#38bdf8" : "#e2e8f0", maxWidth: "65%" }}>
                        {isChild && <span style={{ color: "#38bdf8", marginRight: "0.3rem" }}>↳</span>}
                        {c.name}
                      </span>
                      <span 
                        title={isReview ? "Review: topic attempted or partially mastered; needs reinforcement" : undefined}
                        style={{ fontSize: "0.68rem", fontWeight: "700", padding: "0.15rem 0.4rem", borderRadius: "0.25rem", color: statusColor, backgroundColor: statusBg, cursor: isReview ? "help" : "default" }}
                      >
                        {statusLabel}
                      </span>
                    </div>

                    {/* Progress Bar & BKT Percentage */}
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.4rem" }}>
                      <div style={{ flex: 1, height: "5px", backgroundColor: "#334155", borderRadius: "9999px", overflow: "hidden" }}>
                        <div style={{ height: "100%", width: `${pct}%`, backgroundColor: isMastered ? "#10b981" : (isCurr ? "#38bdf8" : "#f59e0b"), transition: "width 0.4s ease" }} />
                      </div>
                      <span style={{ fontSize: "0.725rem", fontWeight: "700", color: isMastered ? "#34d399" : (isCurr ? "#38bdf8" : "#94a3b8"), minWidth: "30px", textAlign: "right" }}>
                        {pct}%
                      </span>
                    </div>

                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: "0.68rem", color: "#64748b" }}>
                        Diff {c.difficulty || 1}/5
                      </span>
                      <button
                        onClick={() => onDrilldown && onDrilldown(c.concept_id)}
                        disabled={drillDisabled}
                        style={{
                          background: "none",
                          border: "1px solid #334155",
                          borderRadius: "0.25rem",
                          padding: "0.1rem 0.4rem",
                          fontSize: "0.65rem",
                          fontWeight: "600",
                          color: drillDisabled ? "#64748b" : "#38bdf8",
                          cursor: drillDisabled ? "not-allowed" : "pointer",
                          display: "flex",
                          alignItems: "center",
                          gap: "0.2rem",
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

        {/* Document Ingestion Card (RAG) */}
        <div style={{ padding: "1rem", borderTop: "1px solid #1e293b", backgroundColor: "#0b0f19" }}>
          <div style={{ fontSize: "0.725rem", color: "#64748b", fontWeight: "700", marginBottom: "0.45rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Add Custom Textbook / Notes (RAG)
          </div>
          <label style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "0.4rem", padding: "0.5rem", borderRadius: "0.5rem", border: "1px dashed #334155", backgroundColor: "#1e293b", color: "#94a3b8", fontSize: "0.8rem", cursor: "pointer" }}>
            <Upload size={14} />
            <span>{isUploading ? "Embedding..." : "Upload PDF/TXT/MD"}</span>
            <input type="file" accept=".pdf,.txt,.md" onChange={handleFileUpload} disabled={isUploading} style={{ display: "none" }} />
          </label>
          {uploadStatus && (
            <div style={{ fontSize: "0.7rem", color: uploadStatus.includes("✅") ? "#34d399" : "#f87171", marginTop: "0.4rem" }}>
              {uploadStatus}
            </div>
          )}
        </div>
      </div>

      {/* =================================================================== */}
      {/* MAIN WORKSPACE */}
      {/* =================================================================== */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
        {/* Top Header */}
        <div style={{ padding: "0.85rem 1.5rem", borderBottom: "1px solid #1e293b", backgroundColor: "#0f172a", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.85rem", flexWrap: "wrap" }}>
            <span style={{ fontSize: "0.95rem", fontWeight: "700", color: "#e2e8f0" }}>
              {(curriculum || []).find(c => c.concept_id === active_concept)?.name 
                || (active_concept ? active_concept.replace(/_/g, " ").toUpperCase() : "ONBOARDING CALIBRATION")}
            </span>

            {/* Mode Badge */}
            <span style={{ padding: "0.25rem 0.65rem", borderRadius: "9999px", backgroundColor: teaching_mode === "mode_1_qa" ? "rgba(59, 130, 246, 0.15)" : "rgba(16, 185, 129, 0.15)", color: teaching_mode === "mode_1_qa" ? "#60a5fa" : "#34d399", fontSize: "0.75rem", fontWeight: "700", display: "inline-flex", alignItems: "center", gap: "0.3rem" }} title={teaching_mode === "mode_1_qa" ? "Socratic practice and check questions" : "Scaffolded instruction with analogies and worked examples"}>
              {teaching_mode === "mode_1_qa" ? "🎯 Mode 1: Practice" : "📘 Mode 2: Teach First"}
            </span>

            {/* Current Action Badge */}
            {(() => {
              const act = lastAsstMsg?.action || (phase === "diagnostic" ? "diagnostic" : "initial");
              const b = actionBadges[act] || actionBadges.initial;
              return (
                <span style={{ padding: "0.2rem 0.65rem", borderRadius: "9999px", backgroundColor: b.bg, color: b.color, fontSize: "0.75rem", fontWeight: "600" }}>
                  {b.label}
                </span>
              );
            })()}

            {/* Doubts Asked Counter Badge (BKT Invariant) */}
            <span style={{ padding: "0.25rem 0.65rem", borderRadius: "9999px", backgroundColor: "rgba(139, 92, 246, 0.15)", color: "#c084fc", fontSize: "0.75rem", fontWeight: "600", display: "inline-flex", alignItems: "center", gap: "0.3rem" }} title="Doubts are safely routed and never decrease BKT mastery!">
              💬 Doubts: {doubts_asked} <span style={{ fontSize: "0.68rem", color: "#a78bfa" }}>(0 BKT Penalty)</span>
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
            {active_concept && (
              <button
                onClick={() => onDrilldown && onDrilldown(active_concept)}
                disabled={isSending}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.35rem",
                  padding: "0.4rem 0.75rem",
                  borderRadius: "0.5rem",
                  backgroundColor: "#0284c718",
                  border: "1px solid #0284c755",
                  color: "#38bdf8",
                  fontSize: "0.8rem",
                  fontWeight: "600",
                  cursor: isSending ? "not-allowed" : "pointer",
                }}
                title="Drill down into sub-milestones"
              >
                🔬 Drill Down
              </button>
            )}

            <button
              onClick={() => setShowStudio(!showStudio)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.4rem",
                padding: "0.4rem 0.8rem",
                borderRadius: "0.5rem",
                backgroundColor: showStudio ? "#1f6feb" : "transparent",
                border: "1px solid",
                borderColor: showStudio ? "#388bfd" : "#334155",
                color: showStudio ? "#ffffff" : "#cbd5e1",
                fontSize: "0.8rem",
                fontWeight: "600",
                cursor: "pointer",
              }}
            >
              <Code size={14} />
              <span>Studio & Compiler</span>
            </button>

            <button
              onClick={() => setShowDAG(!showDAG)}
              style={{ display: "flex", alignItems: "center", gap: "0.4rem", padding: "0.4rem 0.8rem", borderRadius: "0.5rem", backgroundColor: showDAG ? "#1e293b" : "transparent", border: "1px solid #334155", color: "#cbd5e1", fontSize: "0.8rem", cursor: "pointer" }}
            >
              {showDAG ? <EyeOff size={14} /> : <Eye size={14} />}
              <span>Concept Graph</span>
            </button>
          </div>
        </div>

        {/* Collapsible Mermaid DAG Panel */}
        {showDAG && (
          <div style={{ padding: "1rem", borderBottom: "1px solid #1e293b", backgroundColor: "#090d16", maxHeight: "350px", overflowY: "auto" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem", fontSize: "0.75rem", color: "#94a3b8" }}>
              <span>🟢 Mastered (≥85%) &nbsp;|&nbsp; 🔵 Active &nbsp;|&nbsp; 🟡 Review (60-84%) &nbsp;|&nbsp; ⚪ Pending (&lt;60%)</span>
            </div>
            <MermaidDAG chart={mermaid_dag} title="Curriculum Dependency Graph" />
          </div>
        )}

        {/* Graduation Banner */}
        {is_graduated && (
          <div style={{ margin: "1rem 1.5rem 0", padding: "1.25rem", borderRadius: "0.75rem", backgroundColor: "rgba(16, 185, 129, 0.1)", border: "1px solid rgba(16, 185, 129, 0.3)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <Award size={24} style={{ color: "#34d399" }} />
                <h3 style={{ fontSize: "1.1rem", fontWeight: "700", color: "#34d399" }}>
                  Congratulations! All Concepts Mastered!
                </h3>
              </div>
              <button
                onClick={downloadReport}
                style={{ display: "flex", alignItems: "center", gap: "0.4rem", padding: "0.5rem 1rem", borderRadius: "0.5rem", backgroundColor: "#059669", color: "#ffffff", border: "none", fontWeight: "600", fontSize: "0.85rem", cursor: "pointer" }}
              >
                <Download size={15} /> Download Official Academic Report (.md)
              </button>
            </div>

            {hake_gain && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1rem", marginTop: "0.75rem", padding: "0.75rem", borderRadius: "0.5rem", backgroundColor: "rgba(0, 0, 0, 0.2)" }}>
                <div>
                  <div style={{ fontSize: "0.75rem", color: "#94a3b8" }}>Diagnostic Pre-Baseline</div>
                  <div style={{ fontSize: "1.2rem", fontWeight: "700", color: "#e2e8f0" }}>{((hake_gain.pre ?? 0) * 100).toFixed(1)}%</div>
                </div>
                <div>
                  <div style={{ fontSize: "0.75rem", color: "#94a3b8" }}>Post-Tutoring Mastery</div>
                  <div style={{ fontSize: "1.2rem", fontWeight: "700", color: "#34d399" }}>{((hake_gain.post ?? 0) * 100).toFixed(1)}%</div>
                </div>
                <div>
                  <div style={{ fontSize: "0.75rem", color: "#94a3b8" }}>Hake's Normalized Gain (g)</div>
                  <div style={{ fontSize: "1.2rem", fontWeight: "700", color: "#38bdf8" }}>{(hake_gain.hake_g ?? 0).toFixed(2)}</div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Chat & Studio Container */}
        <div style={{ flex: 1, display: "flex", overflow: "hidden", position: "relative" }}>
          {/* Main Chat Feed */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", height: "100%", overflow: "hidden", minWidth: 0 }}>
            {/* Chat History Stream */}
            <div style={{ flex: 1, overflowY: "auto", padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1.25rem" }}>
              {chat_history.map((msg) => {
                const isAsst = msg.role === "assistant";
                const msgId = msg.id || Math.random().toString();
                const showCitations = expandedCitations[msgId];
                const showMetrics = expandedMetrics[msgId];

                return (
                  <div
                    key={msgId}
                    style={{
                      display: "flex",
                      gap: "0.85rem",
                      alignSelf: isAsst ? "flex-start" : "flex-end",
                      maxWidth: isAsst ? "85%" : "75%",
                    }}
                  >
                    {isAsst && (
                      <div style={{ width: "36px", height: "36px", borderRadius: "0.5rem", backgroundColor: "#1e293b", border: "1px solid #334155", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: "0.25rem" }}>
                        <Brain size={20} style={{ color: "#38bdf8" }} />
                      </div>
                    )}

                    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", width: "100%" }}>
                      {/* Speech Bubble with Formatted Content */}
                      <div
                        style={{
                          padding: "1rem 1.25rem",
                          borderRadius: "1rem",
                          backgroundColor: isAsst ? "#1e293b" : "#0284c7",
                          color: "#f8fafc",
                          fontSize: "0.95rem",
                          lineHeight: "1.6",
                          border: isAsst ? "1px solid #334155" : "none",
                        }}
                      >
                        <FormattedMessageContent content={msg.content} />
                      </div>

                      {/* Socratic Question Callout */}
                      {isAsst && msg.question && (msg.awaiting === "answer" || (!msg.awaiting && msg.action === "probe")) && (
                        <div style={{ padding: "0.85rem 1rem", borderRadius: "0.75rem", backgroundColor: "rgba(56, 189, 248, 0.08)", borderLeft: "3px solid #38bdf8", color: "#e2e8f0", fontSize: "0.925rem" }}>
                          <span style={{ fontWeight: "700", color: "#38bdf8", display: "block", marginBottom: "0.25rem", fontSize: "0.8rem", textTransform: "uppercase" }}>
                            Guiding Socratic Question:
                          </span>
                          {msg.question}
                        </div>
                      )}

                      {/* RAG Citations Accordion */}
                      {isAsst && msg.rag_context?.citations?.length > 0 && (
                        <div style={{ borderRadius: "0.5rem", backgroundColor: "#0f172a", border: "1px solid #1e293b", overflow: "hidden" }}>
                          <button
                            onClick={() => setExpandedCitations(prev => ({ ...prev, [msgId]: !prev[msgId] }))}
                            style={{ width: "100%", padding: "0.5rem 0.75rem", display: "flex", justifyContent: "space-between", alignItems: "center", backgroundColor: "transparent", border: "none", color: "#94a3b8", fontSize: "0.8rem", cursor: "pointer" }}
                          >
                            <span style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                              <BookOpen size={14} style={{ color: "#38bdf8" }} />
                              Authoritative Textbook Citations (Agentic RAG)
                            </span>
                            {showCitations ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                          </button>

                          {showCitations && (
                            <div style={{ padding: "0.75rem", borderTop: "1px solid #1e293b", display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                              {msg.rag_context.citations.map((c, i) => (
                                <div key={i} style={{ padding: "0.5rem", borderRadius: "0.375rem", backgroundColor: "#1e293b", fontSize: "0.8rem" }}>
                                  <div style={{ display: "flex", justifyContent: "space-between", color: "#38bdf8", fontWeight: "600", marginBottom: "0.25rem" }}>
                                    <span>📖 {c.source}</span>
                                    <span>Relevance: {Math.round(c.relevance_score * 100)}%</span>
                                  </div>
                                  <p style={{ color: "#94a3b8", fontStyle: "italic", fontSize: "0.775rem" }}>
                                    "{c.excerpt}"
                                  </p>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Cognitive Reasoning Metrics Accordion */}
                      {isAsst && msg.metadata && (
                        <div style={{ borderRadius: "0.5rem", backgroundColor: "#0f172a", border: "1px solid #1e293b", overflow: "hidden" }}>
                          <button
                            onClick={() => setExpandedMetrics(prev => ({ ...prev, [msgId]: !prev[msgId] }))}
                            style={{ width: "100%", padding: "0.5rem 0.75rem", display: "flex", justifyContent: "space-between", alignItems: "center", backgroundColor: "transparent", border: "none", color: "#64748b", fontSize: "0.75rem", cursor: "pointer" }}
                          >
                            <span>🔍 Agent Reasoning & Critic Audit</span>
                            {showMetrics ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                          </button>

                          {showMetrics && (
                            <div style={{ padding: "0.75rem", borderTop: "1px solid #1e293b", fontSize: "0.775rem", color: "#94a3b8" }}>
                              <div style={{ display: "flex", gap: "1.5rem", marginBottom: "0.5rem" }}>
                                {typeof msg.metadata?.score === "number" && <span>Score: <b>{msg.metadata.score.toFixed(2)}</b></span>}
                                {msg.metadata?.understanding && <span>Understanding: <b>{msg.metadata.understanding}</b></span>}
                                {typeof msg.metadata?.p_know === "number" && <span>BKT P(know): <b>{(msg.metadata.p_know * 100).toFixed(1)}%</b></span>}
                              </div>
                              {msg.metadata?.critic && (
                                <div>
                                  <span>Critic Gate: <b>{msg.metadata.critic.passed ? "PASSED" : "FAILED"}</b> ({msg.metadata.critic.score}/10)</span>
                                  <div style={{ color: "#64748b", fontSize: "0.725rem", marginTop: "0.2rem" }}>
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
              <div ref={messagesEndRef} />
            </div>

            {/* Chat Input & Quick Action Bar */}
            {!is_graduated ? (
              <div style={{ padding: "0.85rem 1.5rem", borderTop: "1px solid #1e293b", backgroundColor: "#0f172a" }}>
                {/* Context-Aware Quick Reply Action Pills */}
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.45rem", marginBottom: "0.65rem" }}>
                  {isLevelPrompt ? (
                    <>
                      <button
                        type="button"
                        onClick={() => onSendMessage("I am a beginner")}
                        disabled={isSending}
                        style={{ padding: "0.3rem 0.75rem", borderRadius: "9999px", backgroundColor: "#065f46", border: "1px solid #10b981", color: "#a7f3d0", fontSize: "0.775rem", fontWeight: "600", cursor: "pointer" }}
                      >
                        🌱 I am a beginner (Teach from scratch)
                      </button>
                      <button
                        type="button"
                        onClick={() => onSendMessage("Some knowledge")}
                        disabled={isSending}
                        style={{ padding: "0.3rem 0.75rem", borderRadius: "9999px", backgroundColor: "#075985", border: "1px solid #38bdf8", color: "#bae6fd", fontSize: "0.775rem", fontWeight: "600", cursor: "pointer" }}
                      >
                        ⚡ Some knowledge (Quick check)
                      </button>
                      <button
                        type="button"
                        onClick={() => onSendMessage("Comfortable")}
                        disabled={isSending}
                        style={{ padding: "0.3rem 0.75rem", borderRadius: "9999px", backgroundColor: "#854d0e", border: "1px solid #f59e0b", color: "#fef08a", fontSize: "0.775rem", fontWeight: "600", cursor: "pointer" }}
                      >
                        🚀 Comfortable (Advanced track)
                      </button>
                    </>
                  ) : isAwaitingContinue ? (
                    <>
                      <button
                        type="button"
                        onClick={() => onSendMessage("continue")}
                        disabled={isSending}
                        style={{ padding: "0.35rem 0.95rem", borderRadius: "9999px", backgroundColor: "#0284c7", border: "1px solid #38bdf8", color: "#ffffff", fontSize: "0.825rem", fontWeight: "700", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: "0.35rem" }}
                      >
                        ▶️ Continue
                      </button>
                      <button
                        type="button"
                        onClick={() => { const el = document.querySelector("textarea, input[type='text']"); el && el.focus(); }}
                        disabled={isSending}
                        style={{ padding: "0.35rem 0.85rem", borderRadius: "9999px", backgroundColor: "#1e293b", border: "1px solid #334155", color: "#cbd5e1", fontSize: "0.8rem", cursor: "pointer" }}
                      >
                        ❓ I have a question
                      </button>
                    </>
                  ) : isAwaitingClarity ? (
                    <>
                      <button
                        type="button"
                        onClick={() => onSendMessage("makes sense, got it")}
                        disabled={isSending}
                        style={{ padding: "0.35rem 0.95rem", borderRadius: "9999px", backgroundColor: "#059669", border: "1px solid #10b981", color: "#ffffff", fontSize: "0.825rem", fontWeight: "700", cursor: "pointer" }}
                      >
                        ✅ Yes, makes sense
                      </button>
                      <button
                        type="button"
                        onClick={() => onSendMessage("could you explain that another way?")}
                        disabled={isSending}
                        style={{ padding: "0.35rem 0.85rem", borderRadius: "9999px", backgroundColor: "#1e293b", border: "1px solid #334155", color: "#fcd34d", fontSize: "0.8rem", cursor: "pointer" }}
                      >
                        🔄 Re-explain another way
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => onSendMessage("Can you show a visual diagram of this concept?")}
                        disabled={isSending}
                        style={{ padding: "0.25rem 0.65rem", borderRadius: "9999px", backgroundColor: "#1e293b", border: "1px solid #334155", color: "#cbd5e1", fontSize: "0.75rem", cursor: "pointer" }}
                      >
                        📊 Show diagram
                      </button>
                      <button
                        type="button"
                        onClick={() => onSendMessage("Can you explain this with a real-world analogy?")}
                        disabled={isSending}
                        style={{ padding: "0.25rem 0.65rem", borderRadius: "9999px", backgroundColor: "#1e293b", border: "1px solid #334155", color: "#cbd5e1", fontSize: "0.75rem", cursor: "pointer" }}
                      >
                        💡 Real-world analogy
                      </button>
                      <button
                        type="button"
                        onClick={() => onSendMessage("Can you walk through a step-by-step example?")}
                        disabled={isSending}
                        style={{ padding: "0.25rem 0.65rem", borderRadius: "9999px", backgroundColor: "#1e293b", border: "1px solid #334155", color: "#cbd5e1", fontSize: "0.75rem", cursor: "pointer" }}
                      >
                        🔍 Worked example
                      </button>
                      <button
                        type="button"
                        onClick={() => onSendMessage("I don't know, could you give me a hint?")}
                        disabled={isSending}
                        style={{ padding: "0.25rem 0.65rem", borderRadius: "9999px", backgroundColor: "#1e293b", border: "1px solid #f59e0b44", color: "#fcd34d", fontSize: "0.75rem", cursor: "pointer" }}
                      >
                        🪜 I don't know (Hint)
                      </button>
                      <button
                        type="button"
                        onClick={() => onSendMessage("Skip this topic for now")}
                        disabled={isSending}
                        style={{ padding: "0.25rem 0.65rem", borderRadius: "9999px", backgroundColor: "#1e293b", border: "1px solid #334155", color: "#94a3b8", fontSize: "0.75rem", cursor: "pointer" }}
                      >
                        ⏭️ Skip topic
                      </button>
                    </>
                  )}
                </div>

                <form onSubmit={handleSubmit} style={{ display: "flex", alignItems: "flex-end", gap: "0.75rem", backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: "0.75rem", padding: "0.5rem 0.75rem" }}>
                  <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Type your explanation, question, or doubt... (Enter to send, Shift+Enter for newline)"
                    disabled={isSending}
                    rows={1}
                    style={{
                      flex: 1,
                      backgroundColor: "transparent",
                      border: "none",
                      outline: "none",
                      color: "#f8fafc",
                      fontSize: "0.95rem",
                      resize: "none",
                      maxHeight: "120px",
                      padding: "0.35rem 0",
                      fontFamily: "inherit",
                    }}
                  />
                  <button
                    type="submit"
                    disabled={!input.trim() || isSending}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: "36px",
                      height: "36px",
                      borderRadius: "0.5rem",
                      backgroundColor: input.trim() && !isSending ? "#0284c7" : "#334155",
                      color: "#ffffff",
                      border: "none",
                      cursor: input.trim() && !isSending ? "pointer" : "not-allowed",
                      flexShrink: 0,
                      transition: "background-color 0.2s ease",
                    }}
                  >
                    {isSending ? (
                      <div style={{ width: "16px", height: "16px", border: "2px solid #ffffff", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
                    ) : (
                      <Send size={16} />
                    )}
                  </button>
                </form>
              </div>
            ) : (
              <div style={{ padding: "1.25rem", borderTop: "1px solid #1e293b", backgroundColor: "#0f172a", textAlign: "center" }}>
                <span style={{ color: "#34d399", fontWeight: "600" }}>🎓 Curriculum Completed! You may start a new topic anytime.</span>
              </div>
            )}
          </div>

          {/* Interactive Studio Side-Panel */}
          {showStudio && (
            <div style={{ width: "520px", maxWidth: "50%", height: "100%", display: "flex", flexDirection: "column", flexShrink: 0 }}>
              <InteractiveStudio
                activeConcept={active_concept}
                onSendToChat={(codePrompt) => onSendMessage(codePrompt)}
                onClose={() => setShowStudio(false)}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
