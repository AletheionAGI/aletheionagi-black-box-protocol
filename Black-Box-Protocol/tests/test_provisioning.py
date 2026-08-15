import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from provision_aletheion import memory_id  # noqa: E402


def test_memory_ids_are_unique_per_frozen_cohort() -> None:
    first = memory_id("a" * 64, "VN-001", "atlas-policy")
    second = memory_id("b" * 64, "VN-001", "atlas-policy")
    assert first != second
    assert first == "bbp:aaaaaaaaaaaa:vn-001:atlas-policy"
