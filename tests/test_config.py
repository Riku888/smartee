"""Tests for the minimal .env loader."""

from smartee.config import load_env


def test_missing_file_returns_empty(tmp_path):
    assert load_env(tmp_path / "nope.env") == []


def test_loads_keys_and_skips_comments_and_blanks(tmp_path, monkeypatch):
    monkeypatch.delenv("SMARTEE_A", raising=False)
    monkeypatch.delenv("SMARTEE_B", raising=False)
    env = tmp_path / ".env"
    env.write_text('# a comment\n\nSMARTEE_A=one\n  SMARTEE_B = "two" \nnot a pair\n')
    loaded = load_env(env)
    assert sorted(loaded) == ["SMARTEE_A", "SMARTEE_B"]
    import os

    assert os.environ["SMARTEE_A"] == "one"
    assert os.environ["SMARTEE_B"] == "two"


def test_does_not_override_an_existing_env_var(tmp_path, monkeypatch):
    monkeypatch.setenv("SMARTEE_C", "from-shell")
    env = tmp_path / ".env"
    env.write_text("SMARTEE_C=from-file\n")
    assert load_env(env) == []
    import os

    assert os.environ["SMARTEE_C"] == "from-shell"
