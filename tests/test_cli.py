from __future__ import annotations

from lenstrace._version import __version__
from lenstrace.cli import DEFAULT_PORT, build_parser, main
from lenstrace.storage.sqlite import SQLiteStorage


class TestParser:
    def test_subcommands_exist(self):
        parser = build_parser()
        for cmd in ("serve", "demo", "info", "version"):
            # parse_args with the subcommand shouldn't raise
            ns = parser.parse_args([cmd] if cmd != "demo" else ["demo", "-n", "1"])
            assert ns.command == cmd

    def test_serve_defaults(self):
        ns = build_parser().parse_args(["serve"])
        assert ns.port == DEFAULT_PORT == 8765
        assert ns.host == "127.0.0.1"

    def test_demo_runs_flag(self):
        ns = build_parser().parse_args(["demo", "-n", "5", "--seed", "3"])
        assert ns.runs == 5
        assert ns.seed == 3


class TestMain:
    def test_version(self, capsys):
        assert main(["version"]) == 0
        assert __version__ in capsys.readouterr().out

    def test_no_command_prints_help(self, capsys):
        assert main([]) == 0
        assert "usage" in capsys.readouterr().out.lower()

    def test_demo_creates_runs(self, tmp_path, capsys):
        db = str(tmp_path / "cli.db")
        rc = main(["demo", "--db", db, "-n", "2", "--seed", "1"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "Generated 2 demo run" in out
        store = SQLiteStorage(db)
        assert store.count_runs() == 2
        store.close()

    def test_info_on_empty(self, tmp_path, capsys):
        db = str(tmp_path / "empty.db")
        assert main(["info", "--db", db]) == 0
        assert "not created yet" in capsys.readouterr().out

    def test_info_with_data(self, tmp_path, capsys):
        db = str(tmp_path / "data.db")
        main(["demo", "--db", db, "-n", "1", "--seed", "1"])
        capsys.readouterr()  # clear
        assert main(["info", "--db", db]) == 0
        assert "1 run" in capsys.readouterr().out
