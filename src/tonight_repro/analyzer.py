from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import ctypes
from dataclasses import asdict, dataclass
from pathlib import Path

TEXT_FILES = {
    "README.md", "README.rst", "requirements.txt", "environment.yml",
    "environment.yaml", "pyproject.toml", "setup.py", "Dockerfile",
}


@dataclass
class Machine:
    os: str
    cpu_count: int
    ram_gb: float
    free_disk_gb: float
    gpu: str | None
    gpu_vram_gb: float | None


@dataclass
class Report:
    verdict: str
    score: int
    machine: dict
    detected: list[str]
    blockers: list[str]
    cautions: list[str]
    good_signs: list[str]
    first_steps: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _ram_gb() -> float:
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                        ("total_phys", ctypes.c_ulonglong), ("avail_phys", ctypes.c_ulonglong),
                        ("total_page", ctypes.c_ulonglong), ("avail_page", ctypes.c_ulonglong),
                        ("total_virtual", ctypes.c_ulonglong), ("avail_virtual", ctypes.c_ulonglong),
                        ("avail_extended", ctypes.c_ulonglong)]
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return round(status.total_phys / 2**30, 1)
        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"],
                text=True, timeout=4, stderr=subprocess.DEVNULL,
            )
            return round(int(out.strip()) / 2**30, 1)
        except Exception:
            pass
    try:
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 1)
    except (AttributeError, ValueError):
        return 0.0


def inspect_machine(path: Path) -> Machine:
    gpu = None
    vram = None
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            text=True, timeout=4, stderr=subprocess.DEVNULL,
        ).splitlines()[0]
        name, memory = out.rsplit(",", 1)
        gpu, vram = name.strip(), round(float(memory.strip()) / 1024, 1)
    except Exception:
        pass
    return Machine(platform.system(), os.cpu_count() or 1, _ram_gb(),
                   round(shutil.disk_usage(path).free / 2**30, 1), gpu, vram)


def _corpus(root: Path) -> tuple[str, set[str]]:
    chunks: list[str] = []
    names: set[str] = set()
    for p in root.rglob("*"):
        if not p.is_file() or any(part.startswith(".") for part in p.relative_to(root).parts):
            continue
        names.add(p.name.lower())
        if p.name in TEXT_FILES or p.name.lower().startswith("readme"):
            try:
                chunks.append(p.read_text(encoding="utf-8", errors="ignore")[:150_000])
            except OSError:
                pass
    return "\n".join(chunks), names


def _numbers(pattern: str, text: str) -> list[float]:
    return [float(x) for x in re.findall(pattern, text, flags=re.I)]


def analyze_repository(root: str | Path, budget_hours: float = 2.0) -> Report:
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f"not a repository directory: {root}")
    text, names = _corpus(root)
    low = text.lower()
    machine = inspect_machine(root)
    score = 100
    detected, blockers, cautions, good = [], [], [], []

    def note(label: str, needle: str):
        if needle in low:
            detected.append(label)

    note("CUDA", "cuda")
    note("Docker", "docker")
    note("Conda", "conda")
    note("PyTorch", "torch")
    note("pretrained checkpoints", "checkpoint")
    note("external datasets", "dataset")

    gpu_required = any(x in low for x in ("gpu required", "requires a gpu", "cuda required", "nvidia gpu"))
    vram_reqs = _numbers(r"(?:vram|gpu memory)[^\n]{0,30}?(\d+(?:\.\d+)?)\s*gb", low)
    disk_reqs = _numbers(r"(?:disk|storage)[^\n]{0,30}?(\d+(?:\.\d+)?)\s*gb", low)
    hour_reqs = _numbers(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)", low)

    if gpu_required and not machine.gpu:
        blockers.append("Repository explicitly requires an NVIDIA GPU, but none was detected.")
        score -= 45
    if vram_reqs and machine.gpu_vram_gb is not None and max(vram_reqs) > machine.gpu_vram_gb:
        blockers.append(f"Documented GPU memory ({max(vram_reqs):g} GB) exceeds local VRAM ({machine.gpu_vram_gb:g} GB).")
        score -= 40
    if disk_reqs and max(disk_reqs) > machine.free_disk_gb:
        blockers.append(f"Documented storage ({max(disk_reqs):g} GB) exceeds free disk ({machine.free_disk_gb:g} GB).")
        score -= 35
    if hour_reqs and min(hour_reqs) > budget_hours:
        cautions.append(f"Shortest documented runtime ({min(hour_reqs):g} h) exceeds tonight's {budget_hours:g} h budget.")
        score -= 20

    if not any(n in names for n in ("requirements.txt", "pyproject.toml", "environment.yml", "environment.yaml")):
        cautions.append("No machine-readable Python environment specification found.")
        score -= 12
    else:
        good.append("Machine-readable environment specification found.")
    if "dockerfile" in names or any(n.startswith("docker-compose") for n in names):
        good.append("Container recipe found; environment drift should be lower.")
        score += 5
    if any("test" in part.lower() for part in names):
        good.append("Tests or test-related files detected.")
        score += 5
    if not any(x in low for x in ("quick start", "quickstart", "demo", "smoke", "example")):
        cautions.append("No obvious quick-start, demo, smoke test, or example path found.")
        score -= 12
    else:
        good.append("A quick/demo/smoke/example path is documented.")
    if "git lfs" in low:
        cautions.append("Git LFS is mentioned; cloning may not include all artifacts by default.")
        score -= 5
    if any(x in low for x in ("request access", "upon request", "license required", "proprietary dataset")):
        blockers.append("A gated, licensed, or request-only artifact is mentioned.")
        score -= 30
    if "download" in low and "dataset" in low:
        cautions.append("External dataset download is likely required; size and access should be checked first.")
        score -= 8

    score = max(0, min(100, score))
    verdict = "GREEN — plausible tonight" if score >= 75 and not blockers else (
        "YELLOW — smoke test only" if score >= 45 else "RED — not tonight")
    first = [
        "Read the exact dataset/checkpoint license before downloading anything.",
        "Create an isolated environment; do not install into base Python.",
        "Run the documented demo/smoke test before any full experiment.",
        "Record the first missing file, version conflict, or OOM as evidence; do not silently patch around it.",
    ]
    return Report(verdict, score, asdict(machine), sorted(set(detected)), blockers, cautions, good, first)
