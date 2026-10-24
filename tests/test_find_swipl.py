"""How the engine is located.

The order is an explicit path, then LOGICLAYER_SWIPL, then the standard
Windows install folder, then the PATH. Nothing about any particular machine's
setup is built in: a copy of SWI-Prolog kept somewhere unusual is reached by
setting LOGICLAYER_SWIPL.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from logiclayer.engines import swipl
from logiclayer.engines.swipl import EngineNotFound, SwiPrologPort, find_swipl

windows_only = pytest.mark.skipif(os.name != "nt", reason="the Program Files lookup is Windows only")


@pytest.fixture
def nothing_installed(monkeypatch, tmp_path):
    """No setting, an empty Program Files, and nothing on the PATH."""
    monkeypatch.delenv("LOGICLAYER_SWIPL", raising=False)
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path / "empty-program-files"))
    monkeypatch.setattr(swipl.shutil, "which", lambda name: None)
    return tmp_path


def fake_binary(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("")
    return path


class TestOrder:
    def test_the_setting_is_used(self, nothing_installed, monkeypatch):
        binary = fake_binary(nothing_installed / "anywhere" / "swipl.exe")
        monkeypatch.setenv("LOGICLAYER_SWIPL", str(binary))
        assert find_swipl() == binary

    def test_an_explicit_path_beats_the_setting(self, nothing_installed, monkeypatch):
        chosen = fake_binary(nothing_installed / "chosen" / "swipl.exe")
        other = fake_binary(nothing_installed / "other" / "swipl.exe")
        monkeypatch.setenv("LOGICLAYER_SWIPL", str(other))
        assert find_swipl(chosen) == chosen

    def test_the_setting_beats_the_path(self, nothing_installed, monkeypatch):
        binary = fake_binary(nothing_installed / "set" / "swipl.exe")
        monkeypatch.setenv("LOGICLAYER_SWIPL", str(binary))
        monkeypatch.setattr(swipl.shutil, "which", lambda name: "C:/elsewhere/swipl.exe")
        assert find_swipl() == binary

    @windows_only
    def test_the_standard_windows_folder_is_found(self, nothing_installed, monkeypatch):
        program_files = nothing_installed / "Program Files"
        binary = fake_binary(program_files / "swipl" / "bin" / "swipl.exe")
        monkeypatch.setenv("PROGRAMFILES", str(program_files))
        assert find_swipl() == binary

    def test_the_path_is_the_last_resort(self, nothing_installed, monkeypatch):
        monkeypatch.setattr(swipl.shutil, "which", lambda name: "/usr/bin/swipl")
        assert find_swipl() == Path("/usr/bin/swipl")

    def test_nothing_found(self, nothing_installed):
        assert find_swipl() is None


class TestNoMachineSetupBuiltIn:
    def test_the_project_folder_is_not_searched(self, nothing_installed):
        """A copy kept inside the project folder is not found unless
        LOGICLAYER_SWIPL points at it. Nothing about one machine's layout is
        built into the lookup."""
        assert find_swipl() is None

    def test_the_error_says_how_to_install(self, nothing_installed):
        with pytest.raises(EngineNotFound) as excinfo:
            SwiPrologPort()
        message = str(excinfo.value)
        assert "winget install SWI-Prolog.SWI-Prolog" in message
        assert "LOGICLAYER_SWIPL" in message
        assert "setup.cmd" not in message
