"""Result files stay out of git, so tests that read them skip when they are absent."""

from pathlib import Path
import unittest

RESULTS = Path(__file__).resolve().parents[3] / 'benchmarks/garden-seasons'


def needs(*names):
    """Skip a test class or method unless every named result file is present locally."""
    missing = [name for name in names if not (RESULTS / name).exists()]
    return unittest.skipIf(bool(missing), 'local results not present: ' + ', '.join(missing))
