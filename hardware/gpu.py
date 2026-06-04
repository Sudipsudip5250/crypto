"""
hardware/gpu.py
---------------
GPU detection and status utilities.

GPU mining (OpenCL / CUDA) is not yet active in this project — XMRig
supports it via flags but requires separate driver setup.  This module
provides detection scaffolding so future GPU support can be enabled here
without touching the rest of the codebase.

Current behaviour
-----------------
• detect_gpu()        — tries to identify any GPU via common CLI tools
• is_gpu_available()  — returns True if at least one GPU was detected
• gpu_xmrig_flags()   — returns extra XMRig flags for GPU mining (empty list for now)
"""

from __future__ import annotations

import logging
import shutil
import subprocess

log = logging.getLogger("xmr-miner")


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def _query_nvidia() -> dict | None:
    """Return basic info about the first NVIDIA GPU via nvidia-smi, or None."""
    if not shutil.which("nvidia-smi"):
        return None
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        parts = [p.strip() for p in out.strip().splitlines()[0].split(",")]
        if len(parts) >= 4:
            return {
                "vendor":     "NVIDIA",
                "name":       parts[0],
                "driver":     parts[1],
                "vram_mb":    parts[2],
                "temp_c":     parts[3],
                "api":        "CUDA",
            }
    except Exception:
        pass
    return None


def _query_amd_rocm() -> dict | None:
    """Return basic info about the first AMD GPU via rocm-smi, or None."""
    if not shutil.which("rocm-smi"):
        return None
    try:
        out = subprocess.check_output(
            ["rocm-smi", "--showproductname", "--csv"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        for line in out.splitlines():
            if "GPU" in line and "card" in line.lower():
                return {"vendor": "AMD", "name": line.strip(), "api": "OpenCL/ROCm"}
    except Exception:
        pass
    return None


def _query_opencl_clinfo() -> dict | None:
    """Return basic OpenCL platform info via clinfo, or None."""
    if not shutil.which("clinfo"):
        return None
    try:
        out = subprocess.check_output(
            ["clinfo", "--list"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        if out.strip():
            return {"vendor": "OpenCL", "name": out.strip().splitlines()[0], "api": "OpenCL"}
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_gpu() -> dict:
    """
    Probe the system for a GPU using common CLI tools.

    Returns a dict with keys:
        available   bool   — True if a GPU was found
        vendor      str    — "NVIDIA" | "AMD" | "OpenCL" | "none"
        name        str    — GPU name / description
        api         str    — "CUDA" | "OpenCL/ROCm" | "OpenCL" | "none"
        details     dict   — raw query result (may be empty)
    """
    for probe in (_query_nvidia, _query_amd_rocm, _query_opencl_clinfo):
        result = probe()
        if result:
            return {
                "available": True,
                "vendor":    result.get("vendor", "Unknown"),
                "name":      result.get("name",   "Unknown"),
                "api":       result.get("api",    "Unknown"),
                "details":   result,
            }

    return {
        "available": False,
        "vendor":    "none",
        "name":      "none",
        "api":       "none",
        "details":   {},
    }


def is_gpu_available() -> bool:
    """Quick check — True if any supported GPU is detected."""
    return detect_gpu()["available"]


def log_gpu_info() -> dict:
    """Detect GPU, log a summary, and return the info dict."""
    info = detect_gpu()
    if info["available"]:
        log.info(
            "GPU detected  |  vendor=%s  name=%s  api=%s",
            info["vendor"], info["name"], info["api"],
        )
        log.info("GPU mining flags are available but not active (CPU-only mode)")
    else:
        log.info("No GPU detected — running in CPU-only mode")
    return info


def gpu_xmrig_flags(gpu_info: dict) -> list[str]:
    """
    Return extra XMRig CLI flags to enable GPU mining.

    Currently returns an empty list (GPU mining not yet enabled).
    To activate in the future, add logic here based on gpu_info["api"].
    """
    # Future example:
    # if gpu_info["api"] == "CUDA":
    #     return ["--cuda", "--cuda-loader=libxmrig-cuda.so"]
    # if "OpenCL" in gpu_info["api"]:
    #     return ["--opencl"]
    return []
