import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("ErrorBoundary caught an error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            padding: "1rem",
            margin: "0.5rem",
            borderRadius: "0.5rem",
            backgroundColor: "#1e1e2e",
            border: "1px solid #ef4444",
            color: "#fca5a5",
            fontSize: "0.85rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem", fontWeight: "700" }}>
            <AlertTriangle size={18} style={{ color: "#ef4444" }} />
            <span>Component Render Error</span>
          </div>
          <p style={{ margin: "0 0 0.5rem 0", color: "#e2e8f0", fontSize: "0.8rem" }}>
            {this.props.fallbackMessage || "An error occurred while displaying this section."}
          </p>
          <button
            type="button"
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "0.3rem",
              padding: "0.3rem 0.6rem",
              borderRadius: "0.25rem",
              backgroundColor: "#374151",
              border: "none",
              color: "#f8fafc",
              fontSize: "0.75rem",
              cursor: "pointer",
            }}
          >
            <RefreshCw size={12} /> Retry
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
