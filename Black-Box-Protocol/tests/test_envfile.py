import os

import pytest

from protocol.envfile import load_env_file


def test_loads_env_without_overwriting_exported_values(tmp_path, monkeypatch) -> None:
    path = tmp_path / ".env"
    path.write_text(
        "# comment\nALPHA=from-file\nBRAVO=\"two words\"\nexport CHARLIE='literal $VALUE'\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ALPHA", "from-shell")
    monkeypatch.delenv("BRAVO", raising=False)
    monkeypatch.delenv("CHARLIE", raising=False)
    assert load_env_file(path) == 2
    assert os.environ["ALPHA"] == "from-shell"
    assert os.environ["BRAVO"] == "two words"
    assert os.environ["CHARLIE"] == "literal $VALUE"


def test_does_not_interpolate_commands_or_variables(tmp_path, monkeypatch) -> None:
    path = tmp_path / ".env"
    path.write_text("SAFE=$(whoami)\nREFERENCE=${HOME}\n", encoding="utf-8")
    monkeypatch.delenv("SAFE", raising=False)
    monkeypatch.delenv("REFERENCE", raising=False)
    load_env_file(path)
    assert os.environ["SAFE"] == "$(whoami)"
    assert os.environ["REFERENCE"] == "${HOME}"


def test_rejects_malformed_lines(tmp_path) -> None:
    path = tmp_path / ".env"
    path.write_text("NOT AN ASSIGNMENT\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected NAME=VALUE"):
        load_env_file(path)
