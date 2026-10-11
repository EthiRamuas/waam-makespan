import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: models 02/04/05 and long sweeps (run once at the end)")
