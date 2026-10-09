"""Cliente Qt opcional; toda análise/conversão/conexão acontece fora da UI thread."""

import json
import sys
from pathlib import Path
from threading import Event
from typing import Any

from PySide6.QtCore import QSettings, Qt, QThread, Signal
from PySide6.QtGui import QCloseEvent, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from craft_bridge.core.pipeline import (
    batch_csv,
    candidate_files,
    convert_file,
    html_report,
    inspect_file,
    preview,
)
from craft_bridge.core.safety import BridgeError, atomic_write, json_text
from craft_bridge.core.validation import validate_plan
from craft_bridge.integrations.effectcraft import apply_plan

STATES = {
    "SUCCESS": "Compatível",
    "PARTIAL": "Parcialmente compatível",
    "UNSUPPORTED": "Não suportado",
    "FAILED": "Falha",
}


class Worker(QThread):
    result = Signal(int, object)
    progress = Signal(int, int)
    message = Signal(str)

    def __init__(
        self,
        jobs: list[tuple[int, Path]],
        action: str,
        out: Path | None,
        options: dict,
        target: str | None,
        parent=None,
    ):
        super().__init__(parent)
        self.jobs, self.action, self.out, self.options, self.target = jobs, action, out, options, target
        self.cancel = Event()

    def run(self) -> None:
        for index, (row, path) in enumerate(self.jobs):
            if self.cancel.is_set():
                self.message.emit(self.tr("Cancelado; os arquivos concluídos foram preservados."))
                break
            try:
                document = inspect_file(path)
                payload, report = preview(
                    document, target=self.target, source_size=self.options.get("source_size")
                )
                if self.action == "convert":
                    if self.out is None:
                        raise BridgeError("Pasta de saída não selecionada.")
                    import hashlib

                    token = hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:10]
                    destination = self.out / (path.name + "." + token + ".json")
                    report = convert_file(path, destination, target=self.target, **self.options)
                self.result.emit(row, {"document": document, "payload": payload, "report": report})
                self.message.emit(f"{path.name}: {report.status}")
            except (BridgeError, OSError) as exc:
                self.result.emit(row, {"error": str(exc)})
                self.message.emit(f"{path.name}: {exc}")
            self.progress.emit(index + 1, len(self.jobs))


class ApplyWorker(QThread):
    completed = Signal(object)

    def __init__(self, payload: dict, layer: str, comp: str | None, parent=None):
        super().__init__(parent)
        self.payload, self.layer, self.comp = payload, layer, comp

    def run(self) -> None:
        try:
            result = apply_plan(validate_plan(self.payload), layer=self.layer, comp=self.comp, confirmed=True)
            self.completed.emit(result)
        except (BridgeError, OSError) as exc:
            self.completed.emit({"error": str(exc)})


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("CraftBridge", "PresetBridge")
        self.paths: list[Path] = []
        self.results: dict[int, dict] = {}
        self.worker: QThread | None = None
        self.close_pending = False
        self.setWindowTitle(self.tr("Craft Preset Bridge"))
        self.resize(1220, 810)
        self.setMinimumSize(940, 650)
        self.setAcceptDrops(True)
        self._build()
        self._theme(self.settings.value("theme", "Escuro"))

    def _build(self) -> None:
        host = QWidget()
        self.setCentralWidget(host)
        layout = QHBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        rail = QFrame()
        rail.setObjectName("rail")
        rail.setFixedWidth(232)
        nav = QVBoxLayout(rail)
        nav.setContentsMargins(24, 30, 24, 24)
        mark = QLabel("CRAFT\nPRESET BRIDGE")
        mark.setObjectName("brand")
        nav.addWidget(mark)
        nav.addSpacing(30)
        nav.addWidget(QLabel(self.tr("DESTINO")))
        self.flow = QComboBox()
        self.flow.addItems([self.tr("Automático"), "Premiere → FilmCraft", "After Effects → EffectCraft"])
        nav.addWidget(self.flow)
        nav.addSpacing(24)
        nav.addWidget(QLabel(self.tr("REFERÊNCIA DO PRESET")))
        self.size_input = QLineEdit()
        self.size_input.setPlaceholderText(self.tr("Ex.: 1920x1080 (opcional)"))
        nav.addWidget(self.size_input)
        self.strict = QCheckBox(self.tr("Rejeitar perdas (strict)"))
        nav.addWidget(self.strict)
        nav.addStretch()
        note = QLabel(self.tr("Leitura local\nSem software Adobe\nSem envio dos seus presets"))
        note.setObjectName("muted")
        nav.addWidget(note)
        nav.addSpacing(22)
        self.theme = QComboBox()
        self.theme.addItems([self.tr("Escuro"), self.tr("Claro")])
        self.theme.setCurrentText(str(self.settings.value("theme", "Escuro")))
        self.theme.currentTextChanged.connect(self._theme)
        nav.addWidget(self.theme)
        layout.addWidget(rail)
        main = QVBoxLayout()
        main.setContentsMargins(30, 26, 30, 24)
        main.setSpacing(15)
        heading = QLabel(self.tr("Presets, com um novo destino."))
        heading.setObjectName("heading")
        main.addWidget(heading)
        subtitle = QLabel(
            self.tr("Analise a compatibilidade, confira as perdas e converta o que tem suporte.")
        )
        subtitle.setObjectName("muted")
        main.addWidget(subtitle)
        self.summary = QLabel(self.tr("0 arquivos na fila  ·  Arraste .prfpset ou .ffx para começar"))
        self.summary.setObjectName("summary")
        main.addWidget(self.summary)
        toolbar = QHBoxLayout()
        self.add_button = QPushButton(self.tr("＋ Adicionar arquivos"))
        self.add_button.clicked.connect(self._select_files)
        self.folder_button = QPushButton(self.tr("Selecionar pasta"))
        self.folder_button.clicked.connect(self._select_folder)
        self.clear_button = QPushButton(self.tr("Limpar fila"))
        self.clear_button.clicked.connect(self._clear)
        for button in (self.add_button, self.folder_button, self.clear_button):
            toolbar.addWidget(button)
        toolbar.addStretch()
        main.addLayout(toolbar)
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            [self.tr("Arquivo"), self.tr("Formato"), self.tr("Efeitos"), self.tr("Compatibilidade")]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._details)
        splitter.addWidget(self.table)
        details_host = QWidget()
        detail_layout = QVBoxLayout(details_host)
        detail_layout.setContentsMargins(0, 8, 0, 0)
        tabs = QHBoxLayout()
        self.details_title = QLabel(self.tr("INSPEÇÃO E DIAGNÓSTICO"))
        tabs.addWidget(self.details_title)
        tabs.addStretch()
        self.detail_mode = QComboBox()
        self.detail_mode.addItems(
            [self.tr("Resumo"), self.tr("Modelo intermediário"), self.tr("Prévia da saída"), self.tr("Logs")]
        )
        self.detail_mode.currentIndexChanged.connect(self._details)
        tabs.addWidget(self.detail_mode)
        detail_layout.addLayout(tabs)
        self.detail_stack = QStackedWidget()
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setPlaceholderText(
            self.tr("Selecione um arquivo e clique em Analisar. Os avisos aparecem aqui.")
        )
        self.logs = QTextEdit()
        self.logs.setReadOnly(True)
        self.detail_stack.addWidget(self.details)
        self.detail_stack.addWidget(self.logs)
        detail_layout.addWidget(self.detail_stack)
        splitter.addWidget(details_host)
        splitter.setSizes([280, 250])
        main.addWidget(splitter, 1)
        destination = QHBoxLayout()
        self.output = QLineEdit(str(self.settings.value("output", str(Path.cwd() / "converted"))))
        self.output.setPlaceholderText(self.tr("Pasta de saída"))
        choose = QPushButton(self.tr("Pasta de saída…"))
        choose.clicked.connect(self._select_output)
        destination.addWidget(self.output, 1)
        destination.addWidget(choose)
        main.addLayout(destination)
        actions = QHBoxLayout()
        self.analyze = QPushButton(self.tr("Analisar"))
        self.analyze.clicked.connect(lambda: self._start("inspect"))
        self.convert = QPushButton(self.tr("Converter fila"))
        self.convert.setObjectName("primary")
        self.convert.clicked.connect(lambda: self._start("convert"))
        self.cancel_button = QPushButton(self.tr("Cancelar"))
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel)
        self.report_button = QPushButton(self.tr("Relatório…"))
        self.report_button.clicked.connect(self._export_report)
        self.apply_button = QPushButton(self.tr("Aplicar…"))
        self.apply_button.setToolTip(self.tr("Revisar e aplicar ao EffectCraft conectado"))
        self.apply_button.clicked.connect(self._apply)
        for button in (self.analyze, self.convert, self.cancel_button, self.report_button, self.apply_button):
            actions.addWidget(button)
        main.addLayout(actions)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        main.addWidget(self.progress)
        layout.addLayout(main, 1)
        self.statusBar().showMessage(self.tr("Pronto · Saídas existentes são preservadas"))

    def _theme(self, theme: Any) -> None:
        dark = theme == "Escuro"
        bg, surface, rail, text, muted, border, accent = (
            ("#14191e", "#1c232a", "#101419", "#edf2f3", "#96a5af", "#34404a", "#9be7ce")
            if dark
            else ("#f3f5f4", "#ffffff", "#e7eeea", "#1b2b26", "#56675f", "#c5d3cb", "#18694c")
        )
        self.setStyleSheet(f"""
            QWidget {{background:{bg};color:{text};font-family:Sans;font-size:13px;}}
            QFrame#rail {{background:{rail};}} QFrame#rail QLabel {{background:{rail};}}
            QLabel#brand {{font-size:20px;font-weight:700;letter-spacing:2px;color:{accent};}}
            QLabel#heading {{font-size:28px;font-weight:650;}} QLabel#muted {{color:{muted};line-height:1.5;}}
            QLabel#summary {{background:{surface};padding:16px;border:1px solid {border};border-radius:8px;}}
            QPushButton {{background:{surface};border:1px solid {border};border-radius:6px;padding:10px 14px;}}
            QPushButton:hover {{border-color:{accent};}} QPushButton:disabled {{color:{muted};}}
            QPushButton#primary {{background:{accent};color:{"#10251c" if dark else "#ffffff"};font-weight:bold;}}
            QLineEdit,QComboBox {{background:{surface};border:1px solid {border};padding:9px;border-radius:5px;}}
            QTableWidget,QTextEdit {{background:{surface};border:1px solid {border};border-radius:6px;selection-background-color:{"#344e45" if dark else "#c9e8d9"};selection-color:{text};}}
            QHeaderView::section {{background:{rail};color:{muted};padding:10px;border:0;border-bottom:1px solid {border};}}
            QProgressBar {{border:0;background:{surface};height:9px;border-radius:4px;text-align:center;}}
            QProgressBar::chunk {{background:{accent};border-radius:4px;}} QStatusBar {{color:{muted};}}
        """)
        self.settings.setValue("theme", theme)

    def add_paths(self, paths: list[Path]) -> None:
        if self.worker and self.worker.isRunning():
            return
        for path in paths:
            path = path.resolve()
            if path in self.paths or not path.is_file():
                continue
            row = self.table.rowCount()
            self.paths.append(path)
            self.table.insertRow(row)
            for col, value in enumerate([path.name, "—", "—", self.tr("Aguardando análise")]):
                item = QTableWidgetItem(value)
                item.setToolTip(str(path))
                self.table.setItem(row, col, item)
            self.table.setRowHeight(row, 39)
        self.summary.setText(self.tr("%n arquivo(s) na fila", "", len(self.paths)))

    def _select_files(self) -> None:
        names, _ = QFileDialog.getOpenFileNames(
            self,
            self.tr("Selecionar presets"),
            "",
            self.tr("Presets (*.ffx *.prfpset);;Todos os arquivos (*)"),
        )
        self.add_paths([Path(n) for n in names])

    def _select_folder(self) -> None:
        name = QFileDialog.getExistingDirectory(self, self.tr("Selecionar pasta de presets"))
        if name:
            self.add_paths(candidate_files(Path(name)))

    def _select_output(self) -> None:
        name = QFileDialog.getExistingDirectory(
            self, self.tr("Selecionar pasta de saída"), self.output.text()
        )
        if name:
            self.output.setText(name)

    def _clear(self) -> None:
        self.paths.clear()
        self.results.clear()
        self.table.setRowCount(0)
        self.details.clear()
        self.summary.setText(self.tr("0 arquivos na fila"))

    def _start(self, action: str) -> None:
        if not self.paths or (self.worker and self.worker.isRunning()):
            return
        size = None
        if self.size_input.text().strip():
            import argparse

            from craft_bridge.cli.main import size_arg

            try:
                size = size_arg(self.size_input.text().strip())
            except argparse.ArgumentTypeError as exc:
                QMessageBox.warning(self, self.tr("Dimensões inválidas"), str(exc))
                return
        out = Path(self.output.text()).expanduser() if self.output.text().strip() else None
        if action == "convert" and out is None:
            QMessageBox.warning(self, self.tr("Pasta necessária"), self.tr("Selecione uma pasta de saída."))
            return
        self.settings.setValue("output", self.output.text())
        options = {"source_size": size, "strict": self.strict.isChecked()}
        target = {0: None, 1: "filmcraft", 2: "effectcraft"}[self.flow.currentIndex()]
        worker = Worker(list(enumerate(self.paths)), action, out, options, target, self)
        self.worker = worker
        worker.result.connect(self._result)
        worker.progress.connect(self._progress)
        worker.message.connect(self.logs.append)
        worker.finished.connect(self._finished)
        self.progress.setMaximum(len(self.paths))
        self.progress.setValue(0)
        self._busy(True)
        self.statusBar().showMessage(self.tr("Processando… Cancelamento disponível entre arquivos."))
        worker.start()

    def _busy(self, value: bool) -> None:
        for widget in (
            self.add_button,
            self.folder_button,
            self.clear_button,
            self.analyze,
            self.convert,
            self.apply_button,
            self.flow,
            self.size_input,
            self.strict,
        ):
            widget.setEnabled(not value)
        self.cancel_button.setEnabled(value and isinstance(self.worker, Worker))

    def _progress(self, done: int, total: int) -> None:
        self.progress.setMaximum(total)
        self.progress.setValue(done)

    def _result(self, row: int, result: dict) -> None:
        self.results[row] = result
        if "error" in result:
            self.table.setItem(row, 3, QTableWidgetItem(self.tr("Falha")))
        else:
            doc, report = result["document"], result["report"]
            self.table.setItem(row, 1, QTableWidgetItem(doc.source.format.upper()))
            self.table.setItem(row, 2, QTableWidgetItem(str(sum(len(p.effects) for p in doc.presets))))
            self.table.setItem(row, 3, QTableWidgetItem(STATES[report.status]))
        self._details()

    def _details(self) -> None:
        mode = self.detail_mode.currentIndex()
        self.detail_stack.setCurrentIndex(1 if mode == 3 else 0)
        row = self.table.currentRow()
        result = self.results.get(row)
        if not result:
            self.details.clear()
            return
        if "error" in result:
            self.details.setPlainText(result["error"])
            return
        doc, report = result["document"], result["report"]
        if mode == 1:
            content = doc.model_dump_json(indent=2)
        elif mode == 2:
            content = json_text(result["payload"])
        else:
            lines = [
                f"{doc.source.path}\n{doc.source.size:,} bytes · {doc.source.detected_version or 'versão não verificada'}",
                f"SHA-256: {doc.source.sha256}\n\nEstado: {report.status}",
                f"Validação: {report.validation}",
            ]
            for effect in report.effects:
                lines.append(
                    f"\n{effect.source} → {effect.target or 'sem equivalente'}\n{effect.status} · parâmetros {effect.parameters_converted}/{effect.parameters_found} · keyframes {effect.keyframes_preserved}/{effect.keyframes_found}"
                )
                lines.extend(f"  • {w.message}" for w in effect.warnings)
            lines.extend(f"\nAviso: {w.message}" for w in report.warnings)
            lines.extend(f"\nErro: {e}" for e in report.errors)
            content = "\n".join(lines)
        self.details.setPlainText(
            content[:500_000]
            + ("\n[Prévia limitada; exporte o relatório completo.]" if len(content) > 500_000 else "")
        )

    def _cancel(self) -> None:
        if isinstance(self.worker, Worker):
            self.worker.cancel.set()
            self.cancel_button.setEnabled(False)

    def _finished(self) -> None:
        self._busy(False)
        self.statusBar().showMessage(self.tr("Concluído · Confira os avisos antes de aplicar os resultados."))
        if self.close_pending:
            self.close()

    def _export_report(self) -> None:
        selected = self.results.get(self.table.currentRow(), {})
        reports = [r["report"] for r in self.results.values() if "report" in r]
        if not reports:
            return
        name, fmt = QFileDialog.getSaveFileName(
            self,
            self.tr("Exportar relatório"),
            "relatorio.html",
            "HTML (*.html);;JSON (*.json);;CSV do lote (*.csv)",
        )
        if not name:
            return
        report = selected.get("report", reports[0])
        content = (
            batch_csv(reports)
            if "CSV" in fmt
            else report.model_dump_json(indent=2)
            if "JSON" in fmt
            else html_report(report)
        )
        try:
            atomic_write(Path(name), content)
        except (BridgeError, OSError) as exc:
            QMessageBox.warning(self, self.tr("Relatório não salvo"), str(exc))

    def _apply(self) -> None:
        selected = self.results.get(self.table.currentRow(), {})
        report = selected.get("report")
        if report and (report.status == "FAILED" or (self.strict.isChecked() and report.status != "SUCCESS")):
            QMessageBox.warning(
                self,
                self.tr("Plano rejeitado"),
                self.tr("O modo strict ou a análise rejeitou este resultado. Confira os avisos."),
            )
            return
        payload = selected.get("payload", {})
        if payload.get("format") != "craftbridge.effectcraft-plan" or not payload.get("effects"):
            QMessageBox.information(
                self,
                self.tr("Nenhum plano selecionado"),
                self.tr("Analise e selecione um FFX com propriedades mapeadas."),
            )
            return
        from PySide6.QtWidgets import QDialog, QDialogButtonBox

        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("Revisar aplicação ao EffectCraft"))
        dialog.resize(760, 570)
        layout = QVBoxLayout(dialog)
        layout.addWidget(
            QLabel(
                self.tr("EffectCraft deve estar aberto com --control 9877. Confira os comandos e o destino.")
            )
        )
        form = QFormLayout()
        layer, comp = QLineEdit("#1"), QLineEdit()
        form.addRow(self.tr("Camada"), layer)
        form.addRow(self.tr("Composição (vazio = ativa)"), comp)
        layout.addLayout(form)
        if any(p.get("keyframes") for e in payload["effects"] for p in e["properties"]):
            layout.addWidget(QLabel(self.tr("Para aplicar os keyframes, a composição de destino será ativada.")))
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(json.dumps(payload["commands"], ensure_ascii=False, indent=2))
        layout.addWidget(text)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(self.tr("Confirmar e aplicar"))
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        worker = ApplyWorker(payload, layer.text().strip(), comp.text().strip() or None, self)
        self.worker = worker
        worker.completed.connect(lambda result: self.logs.append(json_text(result)))
        worker.finished.connect(self._finished)
        self._busy(True)
        worker.start()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = []
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            paths.extend(candidate_files(path) if path.is_dir() else [path])
        self.add_paths(paths)
        event.acceptProposedAction()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.worker and self.worker.isRunning():
            self.close_pending = True
            self._cancel()
            event.ignore()
        else:
            event.accept()


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("Craft Preset Bridge")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
