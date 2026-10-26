import os
import sys
import time
import shutil
import tempfile
import subprocess
from typing import Dict, Any, Optional


TIMEOUT_SECONDS = 5.0
MAX_OUTPUT_CHARS = 10000


def execute_code(
    code: str,
    language: str = "cpp",
    stdin_input: str = "",
    timeout: float = TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """
    Executes code in an isolated temporary sandbox.
    Supports C++20 (via clang++/g++) and Python 3.
    Enforces a strict timeout and output size limit to ensure safety.
    """
    lang = language.lower().strip()
    if lang in ["c++", "cpp", "cxx"]:
        return _execute_cpp(code, stdin_input, timeout)
    elif lang in ["python", "python3", "py"]:
        return _execute_python(code, stdin_input, timeout)
    else:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Unsupported language: '{language}'. Supported languages: 'cpp', 'python'.",
            "exit_code": 1,
            "compilation_failed": False,
            "execution_time_ms": 0.0,
        }


def _execute_cpp(
    code: str,
    stdin_input: str,
    timeout: float,
) -> Dict[str, Any]:
    compiler = shutil.which("clang++") or shutil.which("g++")
    if not compiler:
        return {
            "success": False,
            "stdout": "",
            "stderr": "C++ compiler (clang++ or g++) is not installed on the system.",
            "exit_code": 1,
            "compilation_failed": True,
            "execution_time_ms": 0.0,
        }

    with tempfile.TemporaryDirectory(prefix="sage_cpp_") as tmpdir:
        src_path = os.path.join(tmpdir, "main.cpp")
        bin_path = os.path.join(tmpdir, "main_bin")

        with open(src_path, "w", encoding="utf-8") as f:
            f.write(code)

        compile_cmd = [
            compiler,
            "-std=c++20",
            "-Wall",
            "-Wextra",
            src_path,
            "-o",
            bin_path,
        ]

        t0 = time.perf_counter()
        try:
            compile_res = subprocess.run(
                compile_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir,
            )
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Compilation timed out after {timeout} seconds.",
                "exit_code": -1,
                "compilation_failed": True,
                "execution_time_ms": round((time.perf_counter() - t0) * 1000, 2),
            }

        if compile_res.returncode != 0:
            return {
                "success": False,
                "stdout": "",
                "stderr": compile_res.stderr[:MAX_OUTPUT_CHARS],
                "exit_code": compile_res.returncode,
                "compilation_failed": True,
                "execution_time_ms": round((time.perf_counter() - t0) * 1000, 2),
            }

        t_exec_start = time.perf_counter()
        try:
            run_res = subprocess.run(
                [bin_path],
                input=stdin_input,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir,
            )
            elapsed_ms = round((time.perf_counter() - t_exec_start) * 1000, 2)
            return {
                "success": run_res.returncode == 0,
                "stdout": run_res.stdout[:MAX_OUTPUT_CHARS],
                "stderr": (compile_res.stderr + "\n" + run_res.stderr).strip()[:MAX_OUTPUT_CHARS] if compile_res.stderr else run_res.stderr[:MAX_OUTPUT_CHARS],
                "exit_code": run_res.returncode,
                "compilation_failed": False,
                "execution_time_ms": elapsed_ms,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution timed out after {timeout} seconds. Check for infinite loops or blocking inputs.",
                "exit_code": -1,
                "compilation_failed": False,
                "execution_time_ms": round((time.perf_counter() - t_exec_start) * 1000, 2),
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Runtime error: {str(e)}",
                "exit_code": 1,
                "compilation_failed": False,
                "execution_time_ms": round((time.perf_counter() - t_exec_start) * 1000, 2),
            }


def _execute_python(
    code: str,
    stdin_input: str,
    timeout: float,
) -> Dict[str, Any]:
    python_bin = sys.executable or shutil.which("python3") or shutil.which("python")

    with tempfile.TemporaryDirectory(prefix="sage_py_") as tmpdir:
        src_path = os.path.join(tmpdir, "script.py")
        with open(src_path, "w", encoding="utf-8") as f:
            f.write(code)

        t0 = time.perf_counter()
        try:
            run_res = subprocess.run(
                [python_bin, src_path],
                input=stdin_input,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir,
            )
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            return {
                "success": run_res.returncode == 0,
                "stdout": run_res.stdout[:MAX_OUTPUT_CHARS],
                "stderr": run_res.stderr[:MAX_OUTPUT_CHARS],
                "exit_code": run_res.returncode,
                "compilation_failed": False,
                "execution_time_ms": elapsed_ms,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution timed out after {timeout} seconds. Check for infinite loops or blocking inputs.",
                "exit_code": -1,
                "compilation_failed": False,
                "execution_time_ms": round((time.perf_counter() - t0) * 1000, 2),
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Runtime error: {str(e)}",
                "exit_code": 1,
                "compilation_failed": False,
                "execution_time_ms": round((time.perf_counter() - t0) * 1000, 2),
            }
