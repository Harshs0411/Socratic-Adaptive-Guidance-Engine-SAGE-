import subprocess
import sys
import time
import os

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    print("=" * 70)
    print("🚀 LAUNCHING SAGE FULL-STACK (React 18 + FastAPI + LangGraph)")
    print("=" * 70)

    print("1. Starting FastAPI Backend on http://localhost:8000...")
    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "multi_agent_tutor.api.server:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=root_dir
    )

    time.sleep(2)

    print("2. Starting React Frontend on http://localhost:5173...")
    frontend = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=os.path.join(root_dir, "frontend")
    )

    time.sleep(2)
    print("\n" + "=" * 70)
    print("✅ SAGE PLATFORM IS LIVE & READY!")
    print("🌐 React Web App : http://localhost:5173")
    print("📖 FastAPI Docs  : http://localhost:8000/docs")
    print("=" * 70)
    print("Press Ctrl+C to shut down both servers.\n")

    try:
        backend.wait()
        frontend.wait()
    except KeyboardInterrupt:
        print("\nStopping SAGE servers...")
        backend.terminate()
        frontend.terminate()
        print("Shutdown complete.")

if __name__ == "__main__":
    main()
