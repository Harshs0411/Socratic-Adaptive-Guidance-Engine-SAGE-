import React, { useState } from "react";
import { 
  Brain, Sparkles, ArrowRight, Layers, 
  Compass, Clock, ChevronRight, Zap, CheckCircle2 
} from "lucide-react";

export default function TopicSelection({ onStart, isLoading, pastSessions = [], onResumeSession }) {
  const [topic, setTopic] = useState("");
  const [depthLevel, setDepthLevel] = useState("deep");
  const [studentLevel, setStudentLevel] = useState("beginner");
  const [startFresh, setStartFresh] = useState(false);
  const [activeCategory, setActiveCategory] = useState("cs");

  const categories = {
    cs: {
      name: "Computer Science & Systems",
      icon: "💻",
      topics: [
        { label: "Binary Search & Invariants", icon: "🔍", difficulty: "Beginner • Core" },
        { label: "C++ Memory Layout & RAII", icon: "⚡", difficulty: "Intermediate" },
        { label: "Operating Systems (Virtual Memory)", icon: "🖥️", difficulty: "Advanced" },
        { label: "Distributed Consensus (Raft)", icon: "🌐", difficulty: "Advanced" },
        { label: "Transformer Attention & LLMs", icon: "🧠", difficulty: "Applied Deep" },
      ],
    },
    math: {
      name: "Mathematics & Theory",
      icon: "📐",
      topics: [
        { label: "Singular Value Decomposition (SVD)", icon: "📊", difficulty: "Linear Algebra" },
        { label: "Multivariable Optimization", icon: "📈", difficulty: "Calculus" },
        { label: "Information Theory & Entropy", icon: "🎲", difficulty: "Probability" },
        { label: "Abstract Algebra & Groups", icon: "🔢", difficulty: "Pure Theory" },
      ],
    },
    physics: {
      name: "Physics & Engineering",
      icon: "⚛️",
      topics: [
        { label: "Quantum Superposition & Entanglement", icon: "🌌", difficulty: "Quantum Mechanics" },
        { label: "Thermodynamics & Statistical Mechanics", icon: "🔥", difficulty: "Physics" },
        { label: "Digital Signal Processing (FFT)", icon: "📡", difficulty: "Signal Analysis" },
        { label: "Ohm's Law & Circuit Analysis", icon: "🔋", difficulty: "Electronics" },
      ],
    },
    other: {
      name: "Economics & Biology",
      icon: "🧬",
      topics: [
        { label: "Game Theory & Nash Equilibrium", icon: "♟️", difficulty: "Microeconomics" },
        { label: "CRISPR-Cas9 Gene Editing", icon: "🔬", difficulty: "Biotech" },
        { label: "Central Bank Monetary Policy", icon: "🏦", difficulty: "Macroeconomics" },
      ],
    },
  };

  const studentLevels = [
    {
      id: "beginner",
      name: "Beginner",
      badge: "🌱 Beginner Track",
      color: "#059669",
      subtitle: "Teach-First Mode 2",
      desc: "Starts directly with intuitive real-world analogies, step-by-step worked examples, and zero test pressure.",
    },
    {
      id: "some_knowledge",
      name: "Some Knowledge",
      badge: "⚡ Prior Knowledge",
      color: "#0284c7",
      subtitle: "Diagnostic Baseline",
      desc: "Runs an adaptive diagnostic assessment to calibrate your prerequisite knowledge and build a custom path.",
    },
    {
      id: "comfortable",
      name: "Comfortable",
      badge: "🚀 Advanced Track",
      color: "#d97706",
      subtitle: "Rapid Verification",
      desc: "Starts immediately with Tier 2/3 application challenges and advances quickly once deep mastery is proven.",
    },
  ];

  const depthModes = [
    {
      id: "foundational",
      name: "Foundational Intuition",
      desc: "Mental models, accessible analogies & core definitions (Bloom 1-2)",
      color: "#059669",
      badge: "🟢 Foundational",
    },
    {
      id: "applied",
      name: "Applied Mastery",
      desc: "Practical mechanics, calculations & standard edge cases (Bloom 3-4)",
      color: "#d97706",
      badge: "🟡 Applied",
    },
    {
      id: "deep",
      name: "Deep First Principles",
      desc: "Mathematical proofs, internal mechanisms, and failure modes (Bloom 5-6)",
      color: "#4f46e5",
      badge: "🟣 First Principles",
    },
  ];

  const handleSubmit = (e) => {
    e.preventDefault();
    if (topic.trim() && !isLoading) {
      onStart(topic.trim(), depthLevel, studentLevel, startFresh);
    }
  };

  const handleChipClick = (chosen) => {
    setTopic(chosen);
    if (!isLoading) {
      onStart(chosen, depthLevel, studentLevel, startFresh);
    }
  };

  return (
    <div style={{ position: "relative", minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", padding: "3.5rem 1.5rem 5rem", backgroundColor: "var(--bg-app)", overflow: "hidden" }}>
      {/* Ambient background glow */}
      <div className="ambient-glow" />

      {/* Hero Header */}
      <div style={{ position: "relative", zIndex: 1, textAlign: "center", maxWidth: "800px", marginBottom: "2.5rem" }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem", padding: "0.4rem 1rem", borderRadius: "9999px", backgroundColor: "#eef2ff", border: "1px solid #c7d2fe", color: "var(--indigo-600)", fontSize: "0.825rem", fontWeight: "700", marginBottom: "1.25rem", boxShadow: "0 2px 8px rgba(99, 102, 241, 0.12)" }}>
          <Sparkles size={15} style={{ color: "var(--indigo-600)" }} /> SAGE • Autonomous Socratic Tutoring Engine v2.4
        </div>
        
        <h1 style={{ fontSize: "3.2rem", fontWeight: "800", color: "#0f172a", letterSpacing: "-0.03em", marginBottom: "1.1rem", lineHeight: "1.15" }}>
          Master Any Concept <br />
          <span style={{ background: "linear-gradient(135deg, #0284c7 0%, #4f46e5 50%, #7c3aed 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            From First Principles
          </span>
        </h1>
        
        <p style={{ fontSize: "1.1rem", color: "var(--text-secondary)", lineHeight: "1.65", maxWidth: "680px", margin: "0 auto" }}>
          An adaptive AI tutor powered by Bayesian Knowledge Tracing, dynamic prerequisite DAGs, and rigorous Socratic dialogue. SAGE refuses to give passive answers—it guides you to true algorithmic intuition.
        </p>
      </div>

      {/* Main Search & Topic Input */}
      <form onSubmit={handleSubmit} style={{ position: "relative", zIndex: 1, width: "100%", maxWidth: "720px", marginBottom: "2rem" }}>
        <div 
          style={{
            display: "flex",
            alignItems: "center",
            backgroundColor: "#ffffff",
            border: "1.5pt solid #cbd5e1",
            borderRadius: "1rem",
            padding: "0.5rem 0.6rem 0.5rem 1rem",
            boxShadow: "0 15px 30px -10px rgba(0, 0, 0, 0.08), 0 0 15px rgba(99, 102, 241, 0.06)",
            transition: "all 0.2s ease",
          }}
        >
          <Brain size={24} style={{ color: "var(--indigo-600)", marginRight: "0.75rem", flexShrink: 0 }} />
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="What do you want to master in depth? (e.g. Binary Search, C++ RAII, SVD...)"
            disabled={isLoading}
            style={{
              flex: 1,
              backgroundColor: "transparent",
              border: "none",
              outline: "none",
              color: "#0f172a",
              fontSize: "1.05rem",
              padding: "0.5rem 0",
              fontFamily: "inherit",
            }}
          />
          <button
            type="submit"
            disabled={!topic.trim() || isLoading}
            className="btn-primary"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              borderRadius: "0.75rem",
              padding: "0.75rem 1.4rem",
              fontSize: "0.95rem",
              fontWeight: "700",
              opacity: !topic.trim() || isLoading ? 0.6 : 1,
              cursor: !topic.trim() || isLoading ? "not-allowed" : "pointer",
            }}
          >
            {isLoading ? (
              <span style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span className="typing-dot" style={{ backgroundColor: "#ffffff" }} /> Synthesizing Graph...
              </span>
            ) : (
              <>
                Start Learning <ArrowRight size={17} />
              </>
            )}
          </button>
        </div>

        {/* Start Fresh / Resume Choice Option */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", marginTop: "0.5rem", padding: "0 0.5rem" }}>
          <label style={{ display: "flex", alignItems: "center", gap: "0.45rem", fontSize: "0.78rem", color: startFresh ? "var(--indigo-600)" : "var(--text-muted)", fontWeight: startFresh ? "700" : "500", cursor: "pointer", userSelect: "none" }}>
            <input 
              type="checkbox" 
              checked={startFresh} 
              onChange={(e) => setStartFresh(e.target.checked)} 
              style={{ cursor: "pointer", accentColor: "var(--indigo-600)", width: "14px", height: "14px" }} 
            />
            <span>Start Fresh Attempt (creates new session, reuses curriculum)</span>
          </label>
        </div>
      </form>

      {/* Previous Sessions (If any exist) */}
      {pastSessions.length > 0 && (
        <div style={{ position: "relative", zIndex: 1, width: "100%", maxWidth: "720px", marginBottom: "2rem" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.6rem" }}>
            <span style={{ fontSize: "0.75rem", fontWeight: "700", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", display: "flex", alignItems: "center", gap: "0.35rem" }}>
              <Clock size={13} style={{ color: "var(--indigo-600)" }} /> Continue Your Learning Journey:
            </span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "0.75rem" }}>
            {pastSessions.slice(0, 3).map((s) => (
              <div
                key={s.session_id}
                className="glass-panel glass-panel-hover"
                style={{
                  textAlign: "left",
                  padding: "0.85rem 1rem",
                  borderRadius: "0.75rem",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.45rem",
                  backgroundColor: "#ffffff",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: "0.875rem", fontWeight: "700", color: "#0f172a" }}>{s.topic}</span>
                  <span style={{ fontSize: "0.7rem", padding: "0.15rem 0.5rem", borderRadius: "9999px", backgroundColor: s.is_graduated ? "#ecfdf5" : "#e0f2fe", color: s.is_graduated ? "#059669" : "#0284c7", fontWeight: "700" }}>
                    {s.is_graduated ? "🎓 Mastered" : "📚 In Progress"}
                  </span>
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                  {s.message_count} messages
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "0.2rem", paddingTop: "0.35rem", borderTop: "1px solid var(--border-subtle)" }}>
                  <button
                    type="button"
                    onClick={() => onResumeSession && onResumeSession(s.session_id)}
                    style={{
                      background: "none",
                      border: "none",
                      color: "var(--indigo-600)",
                      fontWeight: "700",
                      fontSize: "0.775rem",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: "0.25rem",
                      padding: "0.2rem 0",
                    }}
                  >
                    Resume <ChevronRight size={13} />
                  </button>
                  <button
                    type="button"
                    onClick={() => onStart(s.topic, depthLevel, studentLevel, true)}
                    style={{
                      background: "#f1f5f9",
                      border: "1px solid var(--border-default)",
                      borderRadius: "0.4rem",
                      color: "var(--text-secondary)",
                      fontWeight: "600",
                      fontSize: "0.7rem",
                      cursor: "pointer",
                      padding: "0.2rem 0.5rem",
                    }}
                    title="Start fresh journey on this topic reusing the curriculum"
                  >
                    🔄 Start Fresh
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Starting Experience Level Selector */}
      <div style={{ position: "relative", zIndex: 1, maxWidth: "720px", width: "100%", marginBottom: "1.75rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.78rem", color: "var(--text-muted)", fontWeight: "700", marginBottom: "0.6rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          <Zap size={14} style={{ color: "var(--emerald-400)" }} /> Your Starting Experience Level:
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem" }}>
          {studentLevels.map((sl) => {
            const isSelected = studentLevel === sl.id;
            return (
              <button
                key={sl.id}
                type="button"
                onClick={() => setStudentLevel(sl.id)}
                className="glass-panel"
                style={{
                  textAlign: "left",
                  padding: "0.85rem 1rem",
                  borderRadius: "0.85rem",
                  borderColor: isSelected ? sl.color : "var(--border-subtle)",
                  backgroundColor: isSelected ? `${sl.color}10` : "#ffffff",
                  boxShadow: isSelected ? `0 0 15px ${sl.color}20` : "0 1px 3px rgba(0, 0, 0, 0.05)",
                  cursor: "pointer",
                  transition: "all 0.2s cubic-bezier(0.16, 1, 0.3, 1)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.25rem" }}>
                  <span style={{ fontSize: "0.85rem", fontWeight: "700", color: isSelected ? sl.color : "#1e293b" }}>
                    {sl.badge}
                  </span>
                  {isSelected && <CheckCircle2 size={14} style={{ color: sl.color }} />}
                </div>
                <div style={{ fontSize: "0.725rem", fontWeight: "600", color: "var(--text-secondary)", marginBottom: "0.35rem" }}>
                  {sl.subtitle}
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", lineHeight: "1.35" }}>
                  {sl.desc}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Target Cognitive Depth Level */}
      <div style={{ position: "relative", zIndex: 1, maxWidth: "720px", width: "100%", marginBottom: "2rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.78rem", color: "var(--text-muted)", fontWeight: "700", marginBottom: "0.6rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          <Layers size={14} style={{ color: "var(--cyan-400)" }} /> Target Cognitive Depth:
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem" }}>
          {depthModes.map((dm) => {
            const isSelected = depthLevel === dm.id;
            return (
              <button
                key={dm.id}
                type="button"
                onClick={() => setDepthLevel(dm.id)}
                className="glass-panel"
                style={{
                  textAlign: "left",
                  padding: "0.85rem 1rem",
                  borderRadius: "0.85rem",
                  borderColor: isSelected ? dm.color : "var(--border-subtle)",
                  backgroundColor: isSelected ? `${dm.color}10` : "#ffffff",
                  boxShadow: isSelected ? `0 0 15px ${dm.color}20` : "0 1px 3px rgba(0, 0, 0, 0.05)",
                  cursor: "pointer",
                  transition: "all 0.2s cubic-bezier(0.16, 1, 0.3, 1)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.35rem" }}>
                  <span style={{ fontSize: "0.85rem", fontWeight: "700", color: isSelected ? dm.color : "#1e293b" }}>
                    {dm.badge}
                  </span>
                  {isSelected && <CheckCircle2 size={14} style={{ color: dm.color }} />}
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", lineHeight: "1.35" }}>
                  {dm.desc}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Curated Multi-Disciplinary Tracks */}
      <div style={{ position: "relative", zIndex: 1, maxWidth: "720px", width: "100%", marginBottom: "3rem" }}>
        {/* Category Tabs */}
        <div style={{ display: "flex", gap: "0.4rem", marginBottom: "0.85rem", borderBottom: "1px solid var(--border-subtle)", paddingBottom: "0.6rem" }}>
          {Object.entries(categories).map(([key, cat]) => (
            <button
              key={key}
              onClick={() => setActiveCategory(key)}
              style={{
                background: "none",
                border: "none",
                borderBottom: activeCategory === key ? "2px solid var(--indigo-600)" : "2px solid transparent",
                padding: "0.4rem 0.75rem",
                color: activeCategory === key ? "var(--indigo-600)" : "var(--text-muted)",
                fontSize: "0.85rem",
                fontWeight: "700",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "0.4rem",
                transition: "all 0.15s ease",
              }}
            >
              <span>{cat.icon}</span> {cat.name}
            </button>
          ))}
        </div>

        {/* Category Topic Chips */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: "0.6rem" }}>
          {categories[activeCategory].topics.map((p) => (
            <button
              key={p.label}
              onClick={() => handleChipClick(p.label)}
              disabled={isLoading}
              className="glass-panel glass-panel-hover"
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-start",
                padding: "0.75rem 1rem",
                borderRadius: "0.75rem",
                cursor: "pointer",
                backgroundColor: "#ffffff",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.2rem" }}>
                <span>{p.icon}</span>
                <span style={{ fontSize: "0.85rem", fontWeight: "700", color: "#0f172a" }}>{p.label}</span>
              </div>
              <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>{p.difficulty}</span>
            </button>
          ))}
        </div>
      </div>

      {/* SAGE Pedagogical Architecture Cards */}
      <div style={{ position: "relative", zIndex: 1, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1rem", maxWidth: "800px", width: "100%" }}>
        <div className="glass-panel" style={{ padding: "1.25rem", borderRadius: "0.85rem", backgroundColor: "#ffffff" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--indigo-600)", fontWeight: "700", marginBottom: "0.5rem" }}>
            <Compass size={18} /> First-Principles Socratic Depth
          </div>
          <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", lineHeight: "1.5" }}>
            Challenges you on edge cases, derivations, and invariant proofs. Refuses to give passive answers.
          </p>
        </div>

        <div className="glass-panel" style={{ padding: "1.25rem", borderRadius: "0.85rem", backgroundColor: "#ffffff" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--emerald-400)", fontWeight: "700", marginBottom: "0.5rem" }}>
            <Layers size={18} /> Dynamic Prerequisite DAGs
          </div>
          <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", lineHeight: "1.5" }}>
            Visualizes conceptual hierarchies with topological dependency trees and multi-resolution milestone drilldowns.
          </p>
        </div>

        <div className="glass-panel" style={{ padding: "1.25rem", borderRadius: "0.85rem", backgroundColor: "#ffffff" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "var(--cyan-400)", fontWeight: "700", marginBottom: "0.5rem" }}>
            <Brain size={18} /> Continuous Bayesian Mastery
          </div>
          <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", lineHeight: "1.5" }}>
            Bayesian Knowledge Tracing models knowledge state continuously. Doubts are celebrated with zero penalty.
          </p>
        </div>
      </div>
    </div>
  );
}
