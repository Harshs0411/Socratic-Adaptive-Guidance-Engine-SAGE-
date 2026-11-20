import React, { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";
import { Code, Eye } from "lucide-react";

mermaid.initialize({
  startOnLoad: false,
  theme: "default",
  securityLevel: "loose",
  suppressErrorRendering: true,
  themeVariables: {
    fontFamily: "Plus Jakarta Sans, Inter, -apple-system, sans-serif",
    fontSize: "13px",
    lineColor: "#64748b",
    edgeLabelBackground: "#f8fafc",
    primaryColor: "#eef2ff",
    primaryBorderColor: "#6366f1",
    primaryTextColor: "#0f172a",
    tertiaryColor: "#f0fdf4",
    secondaryColor: "#f8fafc",
  },
});

function sanitizeMermaid(chart) {
  if (!chart) return "";
  let clean = chart;
  // Ensure unquoted decision nodes with ?, ==, etc. are properly quoted for Mermaid parser
  clean = clean.replace(/([a-zA-Z0-9_]+)\{([^{}"\n]+)\}/g, (match, id, label) => {
    return `${id}{"${label.trim()}"}`;
  });
  return clean;
}

function renderStructuredFallback(chart) {
  const lines = (chart || "").split("\n").map((l) => l.trim()).filter(Boolean);
  const nodes = {};
  const decisions = [];
  const edges = [];

  for (const line of lines) {
    if (
      line.startsWith("graph") ||
      line.startsWith("classDef") ||
      line.startsWith("flowchart") ||
      line.startsWith("class ")
    ) {
      continue;
    }

    // Match decision diamonds { ... } or {{ ... }}
    const decisionMatch = line.match(/([a-zA-Z0-9_]+)\{+["']?(.*?)["']?\}+/);
    if (decisionMatch) {
      nodes[decisionMatch[1]] = { id: decisionMatch[1], label: decisionMatch[2], type: "decision" };
    }

    // Match standard rectangular nodes [ ... ]
    const rectMatch = line.match(/([a-zA-Z0-9_]+)\[+["']?(.*?)["']?\]+/);
    if (rectMatch) {
      nodes[rectMatch[1]] = { id: rectMatch[1], label: rectMatch[2], type: "process" };
    }

    // Match rounded nodes ( ... )
    const roundMatch = line.match(/([a-zA-Z0-9_]+)\(+["']?(.*?)["']?\)+/);
    if (roundMatch && !rectMatch && !decisionMatch) {
      nodes[roundMatch[1]] = { id: roundMatch[1], label: roundMatch[2], type: "terminal" };
    }

    // Match labeled edges: A -- "Yes" --> B, A -- Yes --> B, or A -->|Yes| B
    const edgeMatch =
      line.match(/([a-zA-Z0-9_]+)\s*--\s*["']?([^->"]+)["']?\s*-->\s*([a-zA-Z0-9_]+)/) ||
      line.match(/([a-zA-Z0-9_]+)\s*-->\|([^|]+)\|\s*([a-zA-Z0-9_]+)/);
    if (edgeMatch) {
      edges.push({
        from: edgeMatch[1],
        branch: edgeMatch[2].trim(),
        to: edgeMatch[3],
      });
    }
  }

  // Correlate decision nodes with their branches and targets
  for (const edge of edges) {
    const fromNode = nodes[edge.from];
    const toNode = nodes[edge.to];
    if (fromNode && (fromNode.type === "decision" || edge.branch)) {
      decisions.push({
        condition: fromNode.label || edge.from,
        branch: edge.branch || "Next",
        action: toNode ? toNode.label : edge.to,
      });
    }
  }

  const nodeList = Object.values(nodes);

  if (decisions.length > 0 || nodeList.length > 0) {
    return (
      <div style={{ padding: "1rem", backgroundColor: "#ffffff", display: "flex", flexDirection: "column", gap: "1rem" }}>
        {decisions.length > 0 && (
          <div>
            <div style={{ fontSize: "0.75rem", fontWeight: "700", color: "#4f46e5", marginBottom: "0.45rem", textTransform: "uppercase" }}>
              💎 Decision Logic & Branch Flow
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem", color: "#334155" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border-default)", color: "var(--text-muted)", textAlign: "left" }}>
                  <th style={{ padding: "0.45rem 0.65rem" }}>Condition / Check</th>
                  <th style={{ padding: "0.45rem 0.65rem" }}>Branch</th>
                  <th style={{ padding: "0.45rem 0.65rem" }}>Action / Next Step</th>
                </tr>
              </thead>
              <tbody>
                {decisions.map((d, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                    <td style={{ padding: "0.45rem 0.65rem", fontWeight: "600", color: "#d97706" }}>{d.condition}</td>
                    <td style={{ padding: "0.45rem 0.65rem", color: "#059669", fontWeight: "600" }}>{d.branch}</td>
                    <td style={{ padding: "0.45rem 0.65rem" }}>{d.action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {nodeList.length > 0 && (
          <div>
            <div style={{ fontSize: "0.75rem", fontWeight: "700", color: "var(--text-muted)", marginBottom: "0.45rem", textTransform: "uppercase" }}>
              📋 Architectural Components & States
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem", color: "#334155" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border-default)", color: "var(--text-muted)", textAlign: "left" }}>
                  <th style={{ padding: "0.45rem 0.65rem", width: "25%" }}>Component / Node</th>
                  <th style={{ padding: "0.45rem 0.65rem" }}>Description / Value</th>
                </tr>
              </thead>
              <tbody>
                {nodeList.map((n, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                    <td style={{ padding: "0.45rem 0.65rem", fontWeight: "600", color: n.type === "decision" ? "#d97706" : "#4f46e5" }}>
                      {n.type === "decision" ? `◇ ${n.id}` : n.id}
                    </td>
                    <td style={{ padding: "0.45rem 0.65rem" }}>{n.label}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    );
  }

  return (
    <pre style={{ margin: 0, padding: "1rem", overflowX: "auto", fontSize: "0.8rem", color: "#0f172a", fontFamily: "var(--font-mono)", whiteSpace: "pre-wrap", backgroundColor: "#f8fafc" }}>
      {chart}
    </pre>
  );
}

export default function MermaidDAG({ chart, title = null }) {
  const containerRef = useRef(null);
  const [renderFailed, setRenderFailed] = useState(false);
  const [showRaw, setShowRaw] = useState(false);

  useEffect(() => {
    if (!chart || !containerRef.current) return;
    setRenderFailed(false);
    const id = "mermaid-svg-" + Math.random().toString(36).substring(2, 9);
    const sanitized = sanitizeMermaid(chart);

    mermaid
      .render(id, sanitized)
      .then(({ svg }) => {
        if (containerRef.current) {
          containerRef.current.innerHTML = svg;
          setRenderFailed(false);
        }
      })
      .catch((err) => {
        console.warn("Mermaid render error (falling back to structured text):", err);
        try {
          document.querySelectorAll("[id^='dmermaid']").forEach((el) => el.remove());
        } catch (_) {}
        setRenderFailed(true);
      });
  }, [chart]);

  if (!chart) return null;

  return (
    <div 
      style={{ 
        margin: "0.75rem 0", 
        borderRadius: "0.85rem", 
        overflow: "hidden",
        backgroundColor: "#ffffff",
        border: "1px solid var(--border-subtle)",
        boxShadow: "0 2px 8px rgba(0, 0, 0, 0.04)"
      }}
    >
      <div 
        style={{ 
          display: "flex", 
          justifyContent: "space-between", 
          alignItems: "center", 
          padding: "0.5rem 1rem", 
          borderBottom: "1px solid var(--border-subtle)", 
          backgroundColor: "#f8fafc", 
          fontSize: "0.75rem", 
          color: "var(--text-secondary)",
          fontWeight: "600",
        }}
      >
        <span style={{ color: "var(--text-primary)" }}>{title || "📊 Concept / Flow Diagram"}</span>
        <button
          type="button"
          onClick={() => setShowRaw(!showRaw)}
          style={{ 
            background: "#ffffff", 
            border: "1px solid var(--border-default)", 
            borderRadius: "0.35rem", 
            color: "var(--text-secondary)", 
            padding: "0.2rem 0.55rem", 
            fontSize: "0.7rem", 
            cursor: "pointer", 
            display: "flex", 
            alignItems: "center", 
            gap: "0.3rem" 
          }}
        >
          {showRaw ? <Eye size={12} /> : <Code size={12} />}
          <span>{showRaw ? "Render Diagram" : "Structured Table / Text"}</span>
        </button>
      </div>

      {showRaw || renderFailed ? (
        renderStructuredFallback(chart)
      ) : (
        <div
          ref={containerRef}
          style={{
            overflowX: "auto",
            display: "flex",
            justifyContent: "center",
            padding: "1.25rem",
            backgroundColor: "#ffffff",
          }}
        />
      )}
    </div>
  );
}
