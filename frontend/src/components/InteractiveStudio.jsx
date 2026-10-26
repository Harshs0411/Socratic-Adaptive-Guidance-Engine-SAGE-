import React, { useState } from "react";
import { Play, Sparkles, X, Terminal, Code, BookOpen, AlertTriangle, CheckCircle } from "lucide-react";

export default function InteractiveStudio({ activeConcept, onSendToChat, onClose }) {
  const [language, setLanguage] = useState("cpp"); // "cpp", "python", "notes"
  const [code, setCode] = useState(`// C++20 Interactive Studio
#include <iostream>
#include <vector>
#include <memory>

int main() {
    std::cout << "Hello from C++20 Sandbox!" << std::endl;
    // Practice your active concept here:
    return 0;
}
`);
  const [stdinInput, setStdinInput] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [output, setOutput] = useState(null);

  const templates = {
    cpp: `// C++20 Interactive Studio
#include <iostream>
#include <vector>
#include <memory>

int main() {
    std::cout << "Hello from C++20 Sandbox!" << std::endl;
    // Practice your active concept here:
    return 0;
}
`,
    python: `# Python 3 Mathematical & Algorithmic Studio
import math

def first_principles():
    print("Testing mathematical or algorithmic logic:")
    # Write your formula or algorithm here:
    return math.pi

print(f"Result: {first_principles()}")
`,
    notes: `# Conceptual Scratchpad & Formula Derivations

## Core Mechanism
- Write your thoughts, proofs, or notes here.
- SAGE can critique your reasoning!

Formula derivation:
$$E = mc^2$$
`
  };

  const handleLanguageChange = (newLang) => {
    setLanguage(newLang);
    setCode(templates[newLang] || "");
    setOutput(null);
  };

  const handleRunCode = async () => {
    if (language === "notes") return;
    setIsRunning(true);
    setOutput(null);

    try {
      const res = await fetch("http://localhost:8000/api/code/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code,
          language,
          stdin_input: stdinInput,
        }),
      });
      const data = await res.json();
      setOutput(data);
    } catch (err) {
      setOutput({
        success: false,
        stdout: "",
        stderr: "Failed to connect to backend code runner: " + err.message,
        execution_time_ms: 0,
      });
    } finally {
      setIsRunning(false);
    }
  };

  const handleAskSAGE = () => {
    let reviewPrompt = "";
    if (language === "notes") {
      reviewPrompt = `Here are my notes and derivations on '${activeConcept || "the concept"}':\n\n\`\`\`markdown\n${code}\n\`\`\`\nCan you critique my understanding from first principles?`;
    } else {
      const outputSnippet = output
        ? (output.stdout ? `\nOutput:\n${output.stdout}` : "") + (output.stderr ? `\nCompiler / Error:\n${output.stderr}` : "")
        : "\n(Not yet executed)";
      reviewPrompt = `Here is my ${language.toUpperCase()} code for '${activeConcept || "the active concept"}':\n\n\`\`\`${language}\n${code}\n\`\`\`${outputSnippet}\n\nCan you review this code Socratically and guide me through any edge cases or design improvements?`;
    }
    onSendToChat(reviewPrompt);
  };

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      height: "100%",
      backgroundColor: "#0d1117",
      borderLeft: "1px solid #30363d",
      color: "#c9d1d9",
      fontFamily: "system-ui, -apple-system, sans-serif",
    }}>
      {/* Studio Header */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0.75rem 1rem",
        backgroundColor: "#161b22",
        borderBottom: "1px solid #30363d",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <Code size={18} style={{ color: "#58a6ff" }} />
          <span style={{ fontWeight: "700", fontSize: "0.95rem", color: "#f0f6fc" }}>
            Interactive Studio
          </span>
          {activeConcept && (
            <span style={{
              fontSize: "0.75rem",
              padding: "0.15rem 0.5rem",
              borderRadius: "9999px",
              backgroundColor: "#1f6feb22",
              color: "#58a6ff",
              border: "1px solid #1f6feb55",
            }}>
              {activeConcept.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}
            </span>
          )}
        </div>

        <button
          onClick={onClose}
          style={{
            background: "none",
            border: "none",
            color: "#8b949e",
            cursor: "pointer",
            padding: "0.25rem",
            display: "flex",
            alignItems: "center",
          }}
          title="Close Studio"
        >
          <X size={18} />
        </button>
      </div>

      {/* Language Selector Bar */}
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0.5rem 1rem",
        backgroundColor: "#0d1117",
        borderBottom: "1px solid #21262d",
      }}>
        <div style={{ display: "flex", gap: "0.4rem" }}>
          <button
            onClick={() => handleLanguageChange("cpp")}
            style={{
              padding: "0.3rem 0.75rem",
              borderRadius: "0.375rem",
              fontSize: "0.8rem",
              fontWeight: "600",
              cursor: "pointer",
              border: "1px solid",
              backgroundColor: language === "cpp" ? "#1f6feb" : "#21262d",
              borderColor: language === "cpp" ? "#388bfd" : "#30363d",
              color: language === "cpp" ? "#ffffff" : "#8b949e",
            }}
          >
            ⚡ C++20 (Clang)
          </button>
          <button
            onClick={() => handleLanguageChange("python")}
            style={{
              padding: "0.3rem 0.75rem",
              borderRadius: "0.375rem",
              fontSize: "0.8rem",
              fontWeight: "600",
              cursor: "pointer",
              border: "1px solid",
              backgroundColor: language === "python" ? "#238636" : "#21262d",
              borderColor: language === "python" ? "#2ea043" : "#30363d",
              color: language === "python" ? "#ffffff" : "#8b949e",
            }}
          >
            🐍 Python 3
          </button>
          <button
            onClick={() => handleLanguageChange("notes")}
            style={{
              padding: "0.3rem 0.75rem",
              borderRadius: "0.375rem",
              fontSize: "0.8rem",
              fontWeight: "600",
              cursor: "pointer",
              border: "1px solid",
              backgroundColor: language === "notes" ? "#8957e5" : "#21262d",
              borderColor: language === "notes" ? "#a371f7" : "#30363d",
              color: language === "notes" ? "#ffffff" : "#8b949e",
            }}
          >
            📝 Math / Notes
          </button>
        </div>

        <div style={{ display: "flex", gap: "0.5rem" }}>
          {language !== "notes" && (
            <button
              onClick={handleRunCode}
              disabled={isRunning}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.35rem",
                padding: "0.35rem 0.85rem",
                backgroundColor: isRunning ? "#30363d" : "#238636",
                color: "#ffffff",
                border: "none",
                borderRadius: "0.375rem",
                fontSize: "0.8rem",
                fontWeight: "600",
                cursor: isRunning ? "not-allowed" : "pointer",
              }}
            >
              <Play size={14} fill="currentColor" />
              {isRunning ? "Compiling..." : "Run"}
            </button>
          )}

          <button
            onClick={handleAskSAGE}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.35rem",
              padding: "0.35rem 0.85rem",
              backgroundColor: "#1f6feb",
              color: "#ffffff",
              border: "none",
              borderRadius: "0.375rem",
              fontSize: "0.8rem",
              fontWeight: "600",
              cursor: "pointer",
            }}
            title="Send code/notes to SAGE for Socratic critique"
          >
            <Sparkles size={14} />
            Ask SAGE
          </button>
        </div>
      </div>

      {/* Editor Area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: "220px", position: "relative" }}>
        <textarea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          spellCheck="false"
          style={{
            flex: 1,
            width: "100%",
            backgroundColor: "#0d1117",
            color: "#e6edf3",
            border: "none",
            outline: "none",
            padding: "1rem",
            fontFamily: "'Fira Code', 'JetBrains Mono', Consolas, Monaco, monospace",
            fontSize: "0.875rem",
            lineHeight: "1.5",
            resize: "none",
          }}
          placeholder="Type or paste your code or notes here..."
        />
      </div>

      {/* Terminal / Output Area */}
      {language !== "notes" && (
        <div style={{
          height: "180px",
          backgroundColor: "#010409",
          borderTop: "1px solid #30363d",
          display: "flex",
          flexDirection: "column",
        }}>
          <div style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "0.4rem 0.75rem",
            backgroundColor: "#161b22",
            borderBottom: "1px solid #21262d",
            fontSize: "0.75rem",
            color: "#8b949e",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <Terminal size={14} />
              <span>Terminal & Compiler Diagnostics</span>
            </div>
            {output && (
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                <span>{output.execution_time_ms} ms</span>
                {output.success ? (
                  <span style={{ color: "#3fb950", display: "flex", alignItems: "center", gap: "0.2rem" }}>
                    <CheckCircle size={12} /> Exit 0
                  </span>
                ) : (
                  <span style={{ color: "#f85149", display: "flex", alignItems: "center", gap: "0.2rem" }}>
                    <AlertTriangle size={12} /> Exit {output.exit_code}
                  </span>
                )}
              </div>
            )}
          </div>

          <div style={{
            flex: 1,
            padding: "0.75rem",
            overflowY: "auto",
            fontFamily: "'Fira Code', monospace",
            fontSize: "0.8rem",
            lineHeight: "1.4",
            color: "#c9d1d9",
          }}>
            {!output && !isRunning && (
              <span style={{ color: "#6e7681" }}>Click 'Run' to compile and execute your code in the sandbox.</span>
            )}
            {isRunning && (
              <span style={{ color: "#e3b341" }}>Compiling and executing in isolated sandbox...</span>
            )}
            {output && (
              <>
                {output.stdout && (
                  <pre style={{ margin: 0, whiteSpace: "pre-wrap", color: "#e6edf3" }}>
                    {output.stdout}
                  </pre>
                )}
                {output.stderr && (
                  <pre style={{
                    margin: output.stdout ? "0.5rem 0 0 0" : 0,
                    whiteSpace: "pre-wrap",
                    color: output.compilation_failed ? "#ff7b72" : "#d29922",
                  }}>
                    {output.stderr}
                  </pre>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
