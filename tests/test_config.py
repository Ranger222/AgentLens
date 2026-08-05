from __future__ import annotations

import os

from lenstrace.config import Config, resolve_db_path


class TestResolveDbPath:
    def test_explicit_wins(self, tmp_path):
        p = str(tmp_path / "explicit.db")
        assert resolve_db_path(p) == os.path.abspath(p)

    def test_env_used_when_no_explicit(self, tmp_path, monkeypatch):
        p = str(tmp_path / "env.db")
        monkeypatch.setenv("LENSTRACE_DB", p)
        assert resolve_db_path() == os.path.abspath(p)

    def test_explicit_overrides_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LENSTRACE_DB", str(tmp_path / "env.db"))
        explicit = str(tmp_path / "explicit.db")
        assert resolve_db_path(explicit) == os.path.abspath(explicit)

    def test_default_is_cwd_when_writable(self, tmp_path, monkeypatch):
        monkeypatch.delenv("LENSTRACE_DB", raising=False)
        monkeypatch.chdir(tmp_path)
        assert resolve_db_path() == os.path.join(str(tmp_path), "lenstrace.db")

    def test_expanduser(self):
        assert resolve_db_path("~/x.db").startswith(os.path.expanduser("~"))


class TestConfig:
    def test_from_env_defaults(self, monkeypatch):
        for k in ("LENSTRACE_DISABLED", "LENSTRACE_CAPTURE_IO", "LENSTRACE_MAX_VALUE_LEN"):
            monkeypatch.delenv(k, raising=False)
        cfg = Config.from_env()
        assert cfg.enabled is True
        assert cfg.capture_io is True

    def test_disabled_env(self, monkeypatch):
        monkeypatch.setenv("LENSTRACE_DISABLED", "1")
        assert Config.from_env().enabled is False

    def test_capture_io_env(self, monkeypatch):
        monkeypatch.setenv("LENSTRACE_CAPTURE_IO", "false")
        assert Config.from_env().capture_io is False

    def test_overrides_applied(self):
        cfg = Config.from_env(enabled=False, capture_io=False, max_value_len=10)
        assert cfg.enabled is False
        assert cfg.capture_io is False
        assert cfg.max_value_len == 10
