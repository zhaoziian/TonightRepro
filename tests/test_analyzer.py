import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tonight_repro.analyzer import Machine, analyze_repository


class AnalyzerTests(unittest.TestCase):
    @patch("tonight_repro.analyzer.inspect_machine")
    def test_gpu_gap_is_blocker(self, machine):
        machine.return_value = Machine("Windows", 16, 32, 100, "RTX", 8)
        with tempfile.TemporaryDirectory() as d:
            Path(d, "README.md").write_text("GPU required. GPU memory: 24 GB. Quick start demo.")
            Path(d, "requirements.txt").write_text("torch")
            r = analyze_repository(d)
        self.assertLess(r.score, 75)
        self.assertTrue(any("VRAM" in x for x in r.blockers))

    @patch("tonight_repro.analyzer.inspect_machine")
    def test_small_repo_can_be_green(self, machine):
        machine.return_value = Machine("Windows", 16, 32, 100, None, None)
        with tempfile.TemporaryDirectory() as d:
            Path(d, "README.md").write_text("Quick start: python demo.py")
            Path(d, "pyproject.toml").write_text("[project]")
            Path(d, "test_demo.py").write_text("")
            r = analyze_repository(d)
        self.assertGreaterEqual(r.score, 75)
        self.assertIn("GREEN", r.verdict)


if __name__ == "__main__":
    unittest.main()

