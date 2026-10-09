import json
import subprocess
import sys
import time

import pytest


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "craft_bridge", *map(str, args)], capture_output=True, text=True, timeout=20
    )


def test_cli_inspect_convert_doctor_help(premiere_file, tmp_path):
    result = cli("inspect", premiere_file, "--json")
    assert result.returncode == 0
    assert json.loads(result.stdout)["inspection"]["source"]["format"] == "prfpset"
    out = tmp_path / "cli.json"
    result = cli("convert", premiere_file, "--out", out, "--json")
    assert result.returncode == 0 and out.exists()
    assert json.loads(result.stdout)["status"] == "SUCCESS"
    assert json.loads(cli("doctor", "--json").stdout)["adobe_required"] is False
    assert cli("--help").returncode == 0
    assert cli("mappings", "list").returncode == 0


def test_cli_apply_requires_unequivocal_confirmation(ffx_file, tmp_path):
    plan = tmp_path / "plan.json"
    assert cli("convert", ffx_file, "--out", plan).returncode == 0
    result = cli("apply", plan, "--layer", "#1")
    assert result.returncode == 1 and "--yes" in result.stderr
    assert cli("apply", plan, "--layer", "#1", "--dry-run").returncode == 0


def test_cli_reports_failed_input_and_invalid_args(tmp_path):
    assert cli("inspect", tmp_path / "missing.ffx", "--json").returncode == 1
    assert cli("convert", "x", "--out", "y", "--size", "oops").returncode == 2
    result = cli("inspect", "x", "--max-mib", "-1", "--json")
    assert result.returncode == 1 and json.loads(result.stdout)["status"] == "FAILED"


@pytest.mark.gui
def test_gui_worker_responsiveness_and_theme(premiere_file, tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from craft_bridge.gui.app import MainWindow

    monkeypatch.setattr(
        "craft_bridge.gui.app.QSettings",
        lambda *args: QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat),
    )

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.output.setText(str(tmp_path / "converted"))
    window.add_paths([premiere_file])
    window.show()
    app.processEvents()
    window._start("inspect")
    deadline = time.monotonic() + 10
    while window.worker.isRunning() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()
    assert not window.worker.isRunning()
    assert window.results[0]["report"].status == "SUCCESS"
    window.table.selectRow(0)
    app.processEvents()
    assert "SUCCESS" in window.details.toPlainText()
    for theme in ["Claro", "Escuro"]:
        window._theme(theme)
        app.processEvents()
        assert window.grab().width() > 900
    window.close()
