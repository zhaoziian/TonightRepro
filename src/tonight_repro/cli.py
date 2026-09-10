from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from .analyzer import Report, analyze_repository


def _markdown(r: Report) -> str:
    m = r.machine
    lines = [f"# TonightRepro verdict: {r.verdict}", "", f"**Readiness score:** {r.score}/100", "",
             "## Your machine", "", f"- OS: {m['os']}", f"- CPU threads: {m['cpu_count']}",
             f"- RAM: {m['ram_gb']} GB", f"- Free disk: {m['free_disk_gb']} GB",
             f"- GPU: {m['gpu'] or 'not detected'}" + (f" ({m['gpu_vram_gb']} GB)" if m['gpu_vram_gb'] else "")]
    for title, items in (("Blockers", r.blockers), ("Cautions", r.cautions),
                         ("Good signs", r.good_signs), ("Minimum first steps", r.first_steps)):
        lines += ["", f"## {title}", ""] + ([f"- {x}" for x in items] or ["- None detected."])
    lines += ["", "> Static triage only. TonightRepro never executes the target repository."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Can I reproduce this paper tonight?")
    p.add_argument("target", help="local repository path or public GitHub URL")
    p.add_argument("--hours", type=float, default=2, help="time budget (default: 2)")
    p.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    args = p.parse_args(argv)
    temp = None
    target = args.target
    try:
        if target.startswith(("https://github.com/", "http://github.com/")):
            temp = tempfile.TemporaryDirectory(prefix="tonight-repro-")
            subprocess.run(["git", "clone", "--depth", "1", "--filter=blob:limit=2m", target, temp.name],
                           check=True)
            target = temp.name
        report = analyze_repository(target, args.hours)
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) if args.json else _markdown(report))
        return 0
    finally:
        if temp:
            temp.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())

