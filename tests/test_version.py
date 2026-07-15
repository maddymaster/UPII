"""The version is declared in two places; they must never drift.

pyproject.toml is what PyPI and the wheel carry; upii.__version__ is what the
running CLI reports. A mismatch means a release is mislabelled somewhere.
"""
from pathlib import Path

import pytest

try:  # tomllib is stdlib from 3.11; tomli is the dev-extra backport for 3.10
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - depends on interpreter version
    tomli = pytest.importorskip("tomli", reason="need tomllib (3.11+) or tomli to parse pyproject")
    tomllib = tomli

import upii

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _declared_version() -> str:
    with PYPROJECT.open("rb") as f:
        return tomllib.load(f)["project"]["version"]


@pytest.mark.skipif(not PYPROJECT.exists(), reason="pyproject.toml not present (installed package)")
def test_pyproject_version_matches_dunder_version():
    assert _declared_version() == upii.__version__, (
        f"pyproject.toml declares {_declared_version()!r} but "
        f"upii.__version__ is {upii.__version__!r} — bump both together (see the tag ritual)."
    )
