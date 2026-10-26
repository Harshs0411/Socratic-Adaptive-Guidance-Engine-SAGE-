import React, { useState } from "react";
import { Brain, Sparkles, BookOpen, GitBranch, ArrowRight, ShieldCheck, Database, Layers, Code, Compass } from "lucide-react";

export default function TopicSelection({ onStart, isLoading }) {
  const [topic, setTopic] = useState("");
  const [depthLevel, setDepthLevel] = useState("deep");
  const [studentLevel, setStudentLevel] = useState("beginner");
  const [activeCategory, setActiveCategory] = useState("cs");

  const categories = {
    cs: {
      name: "Computer Science & Systems",
      icon: "💻",
      topics: [
        { label: "Binary Search & Invariants", icon: "🔍" },
        { label: "C++ Memory Layout & RAII", icon: "⚡" },
        { label: "Operating Systems (Virtual Memory)", icon: "🖥️" },
        { label: "Distributed Consensus (Raft)", icon: "🌐" },
        { label: "Transformer Attention & LLMs", icon: "🧠" },
      ],
    },
    math: {
      name: "Mathematics & Theory",
      icon: "📐",
      topics: [
        { label: "Singular Value Decomposition (SVD)", icon: "📊" },
        { label: "Multivariable Optimization", icon: "📈" },
        { label: "Information Theory & Entropy", icon: "🎲" },
        { label: "Abstract Algebra & Groups", icon: "🔢" },
      ],
    },
    physics: {
      name: "Physics & Engineering",
      icon: "⚛️",
      topics: [
        { label: "Quantum Superposition & Entanglement", icon: "🌌" },
        { label: "Thermodynamics & Statistical Mechanics", icon: "🔥" },
        { label: "Digital Signal Processing (FFT)", icon: "📡" },
        { label: "Ohm's Law & Circuit Analysis", icon: "🔋" },
      ],
    },
    other: {
      name: "Economics & Biology",
      icon: "🧬",
      topics: [
        { label: "Game Theory & Nash Equilibrium", icon: "♟️" },
        { label: "CRISPR-Cas9 Gene Editing", icon: "🔬" },
        { label: "Central Bank Monetary Policy", icon: "🏦" },
      ],
    },
  };

  const studentLevels = [
    {
      id: "beginner",
      name: "Beginner",
      badge: "🌱 Beginner",
      color: "#10b981",
      desc: "No diagnostic tests. All initial mastery set to P(L) = 0.0. Starts immediately with intuitive analogies, worked examples, and teach-first Mode 2.",
    },
    {
      id: "some_knowledge",
      name: "Some Knowledge",
      badge: "⚡ Some Knowledge",
      color: "#38bdf8",
      desc: "Full diagnostic assessment. Evaluates core concepts to calibrate baseline priors, with hints if stuck, then adapts the curriculum.",
    },
    {
      id: "comfortable",
      name: "Comfortable",
      badge: "🚀 Comfortable",
      color: "#f59e0b",
      desc: "Full diagnostic starting with harder tier 2 application questions. Confirms deep knowledge and advances quickly once proven.",
    },
  ];

  const depthModes = [
    {
      id: "foundational",
      name: "Foundational Intuition",
      desc: "Mental models, accessible analogies & core definitions (Bloom 1-2)",
      color: "#34d399",
      badge: "🟢 Foundational",
    },
    {
      id: "applied",
      name: "Applied Mastery",
      desc: "Practical mechanics, problem solving & standard pitfalls (Bloom 3-4)",
      color: "#fbbf24",
      badge: "🟡 Applied",
    },
    {
      id: "deep",
      name: "Deep First Principles",
      desc: "Mathematical proofs, internal mechanisms, edge cases & failure modes (Bloom 5-6)",
      color: "#f43f5e",
      badge: "🔴 Deep Mastery",
    },
  ];

  const handleSubmit = (e) => {
    e.preventDefault();
    if (topic.trim() && !isLoading) {
      onStart(topic.trim(), depthLevel, studentLevel);
    }
  };

  const handleChipClick = (chosen) => {
    setTopic(chosen);
    if (!isLoading) {
      onStart(chosen, depthLevel, studentLevel);
    }
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", padding: "2.5rem 1.5rem", backgroundColor: "#0b0f19" }}>
      {/* Brand Header */}
      <div style={{ textAlign: "center", maxWidth: "780px", marginBottom: "2rem" }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem", padding: "0.4rem 1rem", borderRadius: "9999px", backgroundColor: "#1e293b", border: "1px solid #334155", color: "#60a5fa", fontSize: "0.875rem", fontWeight: "600", marginBottom: "1.25rem" }}>
          <Sparkles size={16} /> Autonomous Universal Socratic Tutoring System
        </div>
        <h1 style={{ fontSize: "2.75rem", fontWeight: "800", color: "#f8fafc", letterSpacing: "-0.025em", marginBottom: "1rem", lineHeight: "1.2" }}>
          Master Any Topic <span style={{ color: "#38bdf8" }}>Till Deep Understanding</span>
        </h1>
        <p style={{ fontSize: "1.05rem", color: "#94a3b8", lineHeight: "1.6" }}>
          From low-level C++ systems and Quantum Mechanics to Multivariable Calculus and Game Theory. SAGE generates an adaptive prerequisite graph, challenges your reasoning with Socratic inquiry, and guides you to deep first-principles mastery.
        </p>
      </div>

      {/* Main Input Form */}
      <form onSubmit={handleSubmit} style={{ width: "100%", maxWidth: "720px", marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", backgroundColor: "#1e293b", border: "2px solid #334155", borderRadius: "1rem", padding: "0.5rem 0.75rem", boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.5)" }}>
          <Brain size={24} style={{ color: "#38bdf8", marginLeft: "0.5rem", marginRight: "0.75rem" }} />
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="What subject or concept do you want to master in depth? (e.g. C++, SVD, Quantum Mechanics...)"
            disabled={isLoading}
            style={{ flex: 1, backgroundColor: "transparent", border: "none", outline: "none", color: "#f8fafc", fontSize: "1.05rem", padding: "0.5rem 0" }}
          />
          <button
            type="submit"
            disabled={!topic.trim() || isLoading}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              backgroundColor: topic.trim() && !isLoading ? "#0284c7" : "#334155",
              color: "#ffffff",
              border: "none",
              borderRadius: "0.75rem",
              padding: "0.75rem 1.5rem",
              fontWeight: "600",
              cursor: topic.trim() && !isLoading ? "pointer" : "not-allowed",
              transition: "all 0.2s ease",
            }}
          >
            {isLoading ? "Synthesizing..." : "Start Learning"}
            <ArrowRight size={18} />
          </button>
        </div>
      </form>

      {/* Student Starting Level Selector */}
      <div style={{ maxWidth: "720px", width: "100%", marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.8rem", color: "#94a3b8", fontWeight: "700", marginBottom: "0.6rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          <Brain size={14} style={{ color: "#10b981" }} /> Your Starting Experience Level:
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem" }}>
          {studentLevels.map((sl) => {
            const isSelected = studentLevel === sl.id;
            return (
              <button
                key={sl.id}
                type="button"
                onClick={() => setStudentLevel(sl.id)}
                style={{
                  textAlign: "left",
                  padding: "0.75rem 0.85rem",
                  borderRadius: "0.75rem",
                  border: `2px solid ${isSelected ? sl.color : "#1e293b"}`,
                  backgroundColor: isSelected ? `${sl.color}15` : "#0f172a",
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.25rem" }}>
                  <span style={{ fontSize: "0.85rem", fontWeight: "700", color: isSelected ? sl.color : "#e2e8f0" }}>
                    {sl.badge}
                  </span>
                </div>
                <div style={{ fontSize: "0.75rem", color: "#94a3b8", lineHeight: "1.3" }}>
                  {sl.desc}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Cognitive Depth Level Selector */}
      <div style={{ maxWidth: "720px", width: "100%", marginBottom: "2rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.8rem", color: "#94a3b8", fontWeight: "700", marginBottom: "0.6rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
          <Layers size={14} style={{ color: "#38bdf8" }} /> Select Target Cognitive Depth:
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "0.75rem" }}>
          {depthModes.map((dm) => {
            const isSelected = depthLevel === dm.id;
            return (
              <button
                key={dm.id}
                type="button"
                onClick={() => setDepthLevel(dm.id)}
                style={{
                  textAlign: "left",
                  padding: "0.75rem 0.85rem",
                  borderRadius: "0.75rem",
                  border: `2px solid ${isSelected ? dm.color : "#1e293b"}`,
                  backgroundColor: isSelected ? `${dm.color}15` : "#0f172a",
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.25rem" }}>
                  <span style={{ fontSize: "0.85rem", fontWeight: "700", color: isSelected ? dm.color : "#e2e8f0" }}>
                    {dm.badge}
                  </span>
                </div>
                <div style={{ fontSize: "0.75rem", color: "#94a3b8", lineHeight: "1.3" }}>
                  {dm.desc}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Curated Multi-Disciplinary Tracks */}
      <div style={{ maxWidth: "720px", width: "100%", marginBottom: "2.5rem" }}>
        {/* Category Tabs */}
        <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem", borderBottom: "1px solid #1e293b", paddingBottom: "0.5rem" }}>
          {Object.entries(categories).map(([key, cat]) => (
            <button
              key={key}
              onClick={() => setActiveCategory(key)}
              style={{
                background: "none",
                border: "none",
                borderBottom: activeCategory === key ? "2px solid #38bdf8" : "2px solid transparent",
                padding: "0.3rem 0.6rem",
                color: activeCategory === key ? "#38bdf8" : "#64748b",
                fontSize: "0.85rem",
                fontWeight: "600",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "0.35rem",
              }}
            >
              <span>{cat.icon}</span> {cat.name}
            </button>
          ))}
        </div>

        {/* Category Chips */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
          {categories[activeCategory].topics.map((p) => (
            <button
              key={p.label}
              onClick={() => handleChipClick(p.label)}
              disabled={isLoading}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.4rem",
                padding: "0.45rem 0.8rem",
                borderRadius: "0.5rem",
                backgroundColor: "#0f172a",
                border: "1px solid #334155",
                color: "#cbd5e1",
                fontSize: "0.825rem",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
              onMouseOver={(e) => (e.currentTarget.style.borderColor = "#38bdf8")}
              onMouseOut={(e) => (e.currentTarget.style.borderColor = "#334155")}
            >
              <span>{p.icon}</span> {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Architecture Highlights */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: "1rem", maxWidth: "800px", width: "100%" }}>
        <div style={{ padding: "1.1rem", borderRadius: "0.75rem", backgroundColor: "#0f172a", border: "1px solid #1e293b" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#38bdf8", fontWeight: "600", marginBottom: "0.4rem" }}>
            <Compass size={18} /> First-Principles Socratic Depth
          </div>
          <p style={{ fontSize: "0.8rem", color: "#94a3b8", lineHeight: "1.4" }}>
            Challenges you on boundary conditions, trade-offs, and derivations instead of passive recall.
          </p>
        </div>

        <div style={{ padding: "1.1rem", borderRadius: "0.75rem", backgroundColor: "#0f172a", border: "1px solid #1e293b" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#34d399", fontWeight: "600", marginBottom: "0.4rem" }}>
            <Code size={18} /> Interactive Code & Math Studio
          </div>
          <p style={{ fontSize: "0.8rem", color: "#94a3b8", lineHeight: "1.4" }}>
            Compile C++20, execute Python calculations, and verify math derivations in a sandboxed lab.
          </p>
        </div>

        <div style={{ padding: "1.1rem", borderRadius: "0.75rem", backgroundColor: "#0f172a", border: "1px solid #1e293b" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#fbbf24", fontWeight: "600", marginBottom: "0.4rem" }}>
            <GitBranch size={18} /> Concept Drilldown DAG
          </div>
          <p style={{ fontSize: "0.8rem", color: "#94a3b8", lineHeight: "1.4" }}>
            Drill down into any node in the prerequisite graph to unpack specialized sub-facets in depth.
          </p>
        </div>
      </div>
    </div>
  );
}
