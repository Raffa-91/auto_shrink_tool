from PyQt5 import QtWidgets, QtCore, QtGui
import os
from logging_setup import main_logger

class OutputDialog(QtWidgets.QDialog):
    append_text_signal = QtCore.pyqtSignal(str)

    def __init__(self, shrink_log_path):
        super().__init__()
        self.setWindowTitle("Ausgabe des Shrink-Skripts")
        self.resize(800, 600)
        self.layout = QtWidgets.QVBoxLayout()

        self.output_text = QtWidgets.QPlainTextEdit()
        self.output_text.setReadOnly(True)
        self.layout.addWidget(self.output_text)

        self.close_button = QtWidgets.QPushButton()
        self.close_button.clicked.connect(self.close)
        self.layout.addWidget(self.close_button)

        self.view_shrink_log_button = QtWidgets.QPushButton("Shrink-Log anzeigen")
        self.view_shrink_log_button.clicked.connect(lambda: self.open_shrink_log(shrink_log_path))
        self.layout.addWidget(self.view_shrink_log_button)

        self.setLayout(self.layout)
        self.append_text_signal.connect(self.output_text.appendPlainText)

        self.remaining_time = 300
        self.update_close_button()
        self.auto_close_timer = QtCore.QTimer(self)
        self.auto_close_timer.setInterval(1000)
        self.auto_close_timer.timeout.connect(self.update_timer)
        self.auto_close_timer.start()

    def append_output(self, text):
        self.append_text_signal.emit(text)

    def update_close_button(self):
        minutes = self.remaining_time // 60
        seconds = self.remaining_time % 60
        self.close_button.setText(f"Schließen ({minutes:02d}:{seconds:02d})")

    def update_timer(self):
        self.remaining_time -= 1
        if self.remaining_time <= 0:
            self.auto_close_timer.stop()
            self.close()
        else:
            self.update_close_button()

    def open_shrink_log(self, shrink_log_path):
        if os.path.exists(shrink_log_path):
            try:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(shrink_log_path))
                main_logger.info(f"[LOGVIEWER] Öffne Shrink-Log: {shrink_log_path}")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Fehler", f"Kann Shrink-Log nicht öffnen: {e}")
                main_logger.error(f"[LOGVIEWER ERROR] Kann Shrink-Log nicht öffnen: {e}")
        else:
            QtWidgets.QMessageBox.information(self, "Info", "Shrink-Log-Datei nicht gefunden.")
            main_logger.warning("[LOGVIEWER] Shrink-Log-Datei nicht gefunden.")

    def closeEvent(self, event):
        self.auto_close_timer.stop()
        super().closeEvent(event)
class SettingsDialog(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Einstellungen')
        self.setFixedSize(400, 200)
        layout = QtWidgets.QVBoxLayout()

        delete_backups_layout = QtWidgets.QHBoxLayout()
        self.delete_backups_switch = QtWidgets.QCheckBox("Ältere Backups löschen")
        delete_backups_layout.addWidget(self.delete_backups_switch)
        self.hours_input = QtWidgets.QSpinBox()
        self.hours_input.setRange(1, 5000)
        self.hours_input.setValue(168)
        delete_backups_layout.addWidget(self.hours_input)
        delete_backups_layout.addWidget(QtWidgets.QLabel("Stunden"))
        layout.addLayout(delete_backups_layout)

        logging_layout = QtWidgets.QHBoxLayout()
        self.logging_switch = QtWidgets.QCheckBox("Log-Datei erstellen")
        logging_layout.addWidget(self.logging_switch)
        self.advanced_logging_checkbox = QtWidgets.QCheckBox("Erweitertes Log")
        logging_layout.addWidget(self.advanced_logging_checkbox)
        layout.addLayout(logging_layout)

        buttons_layout = QtWidgets.QHBoxLayout()
        self.save_button = QtWidgets.QPushButton('Einstellungen speichern')
        self.save_button.clicked.connect(self.save_settings)
        buttons_layout.addWidget(self.save_button)
        self.close_button = QtWidgets.QPushButton('Schließen')
        self.close_button.clicked.connect(self.close)
        buttons_layout.addWidget(self.close_button)
        layout.addLayout(buttons_layout)

        self.setLayout(layout)
        self.load_settings()

    def save_settings(self):
        settings = {
            'logging_enabled': self.logging_switch.isChecked(),
            'advanced_logging': self.advanced_logging_checkbox.isChecked(),
            'delete_backups': self.delete_backups_switch.isChecked(),
            'delete_hours': self.hours_input.value()
        }
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f)
        QtWidgets.QMessageBox.information(self, 'Einstellungen', 'Einstellungen gespeichert.')
        main_logger.info("[SETTINGS] Einstellungen über den SettingsDialog gespeichert.")

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                settings = json.load(f)
            self.logging_switch.setChecked(settings.get('logging_enabled', False))
            self.advanced_logging_checkbox.setChecked(settings.get('advanced_logging', False))
            self.delete_backups_switch.setChecked(settings.get('delete_backups', False))
            self.hours_input.setValue(settings.get('delete_hours', 168))

class LogViewer(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Log Viewer")
        self.resize(1000, 700)
        self.layout = QtWidgets.QVBoxLayout()

        self.tabs = QtWidgets.QTabWidget()
        self.layout.addWidget(self.tabs)

        self.main_log_tab = QtWidgets.QWidget()
        self.main_log_layout = QtWidgets.QVBoxLayout()
        self.main_log_text = QtWidgets.QPlainTextEdit()
        self.main_log_text.setReadOnly(True)
        self.main_log_layout.addWidget(self.main_log_text)

        self.refresh_main_log_button = QtWidgets.QPushButton('Haupt-Log aktualisieren')
        self.refresh_main_log_button.clicked.connect(self.load_main_logs)
        self.main_log_layout.addWidget(self.refresh_main_log_button)

        self.main_log_tab.setLayout(self.main_log_layout)
        self.tabs.addTab(self.main_log_tab, "Haupt-Log")

        self.shrink_logs_tab = QtWidgets.QWidget()
        self.shrink_logs_layout = QtWidgets.QVBoxLayout()

        self.shrink_logs_list = QtWidgets.QListWidget()
        self.shrink_logs_layout.addWidget(self.shrink_logs_list)

        self.refresh_shrink_logs_button = QtWidgets.QPushButton('Shrink-Logs aktualisieren')
        self.refresh_shrink_logs_button.clicked.connect(self.load_shrink_logs)
        self.shrink_logs_layout.addWidget(self.refresh_shrink_logs_button)

        self.shrink_logs_tab.setLayout(self.shrink_logs_layout)
        self.tabs.addTab(self.shrink_logs_tab, "Shrink-Logs")

        self.setLayout(self.layout)
        self.load_main_logs()
        self.load_shrink_logs()

    def load_main_logs(self):
        if os.path.exists(main_log_filename):
            with open(main_log_filename, 'r') as f:
                log_content = f.read()
            self.main_log_text.setPlainText(log_content)
            main_logger.debug("[LOGVIEWER] Haupt-Log geladen.")
        else:
            self.main_log_text.setPlainText("Keine Haupt-Log-Datei gefunden.")
            main_logger.warning("[LOGVIEWER] Haupt-Log-Datei nicht gefunden.")

    def load_shrink_logs(self):
        self.shrink_logs_list.clear()
        for root, dirs, files in os.walk(BACKUP_FOLDER):
            if "shrink.log" in files:
                shrink_log_path = os.path.join(root, "shrink.log")
                backup_folder = os.path.basename(root)
                list_item = QtWidgets.QListWidgetItem(backup_folder)
                widget = QtWidgets.QWidget()
                layout = QtWidgets.QHBoxLayout()
                layout.setContentsMargins(5, 5, 5, 5)

                label = QtWidgets.QLabel(backup_folder)
                view_button = QtWidgets.QPushButton("Shrink-Log anzeigen")
                view_button.clicked.connect(lambda checked, path=shrink_log_path: self.open_shrink_log(path))

                layout.addWidget(label)
                layout.addStretch()
                layout.addWidget(view_button)
                widget.setLayout(layout)

                list_item.setSizeHint(widget.sizeHint())
                self.shrink_logs_list.addItem(list_item)
                self.shrink_logs_list.setItemWidget(list_item, widget)
        main_logger.debug("[LOGVIEWER] Shrink-Logs geladen.")

    def open_shrink_log(self, shrink_log_path):
        if os.path.exists(shrink_log_path):
            try:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(shrink_log_path))
                main_logger.info(f"[LOGVIEWER] Öffne Shrink-Log: {shrink_log_path}")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Fehler", f"Kann Shrink-Log nicht öffnen: {e}")
                main_logger.error(f"[LOGVIEWER ERROR] Kann Shrink-Log nicht öffnen: {e}")
        else:
            QtWidgets.QMessageBox.information(self, "Info", "Shrink-Log-Datei nicht gefunden.")
            main_logger.warning("[LOGVIEWER] Shrink-Log-Datei nicht gefunden.")
