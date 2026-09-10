# TonightRepro 🌙

**Can I reproduce this paper tonight—or should I stop before downloading 200 GB?**

TonightRepro is a tiny, local-first preflight checker for research-code repositories. It compares documented requirements with your machine and time budget, then returns a blunt `GREEN`, `YELLOW`, or `RED` verdict.

It never installs dependencies, downloads datasets, or executes target repository code.

## Why this exists

Most reproducibility tools start after setup. The expensive mistakes happen before setup: hidden 24 GB VRAM requirements, gated datasets, missing checkpoints, Linux-only tooling, or a “quick demo” that actually takes 12 hours.

TonightRepro is deliberately narrower than automated research agents and reproducibility frameworks:

| Tool type | Main question |
|---|---|
| Paper recommender | What should I read? |
| Reproduction agent | Can an agent run the experiment? |
| Environment capture | What exactly was installed? |
| **TonightRepro** | **Is this worth attempting on this machine tonight?** |

## Quick start

```bash
pip install -e .
tonight-repro path/to/paper-repo --hours 2
tonight-repro https://github.com/owner/paper-repo --hours 1 --json
```

## What it checks

- local CPU, RAM, free disk, NVIDIA GPU and VRAM
- documented CUDA/GPU, storage and runtime requirements
- gated or licensed artifacts
- external dataset and Git LFS risk
- environment specifications, containers, tests and smoke/demo paths
- a conservative minimum-first-steps checklist

## Honest limitations

This is heuristic static analysis, not a promise of reproducibility. README files can be incomplete, hardware requirements may appear only in a paper, and runtime estimates vary. The report shows what it detected so you can challenge it.

## Development

```bash
python -m unittest discover -s tests -v
```

## Privacy and safety

Local paths stay local. For a GitHub URL, the CLI makes a shallow temporary clone, reads documentation and manifest files, and deletes the clone. It never runs code from the inspected repository.

## License

MIT

