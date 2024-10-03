# V0.1a/gui.py
import os
import re
import json
import shutil
import datetime
import subprocess
import threading
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import QUrl, pyqtSignal, Qt
from PyQt5.QtGui import QDesktopServices
from log_handler import logger  # Zentralen Logger importieren

# PiShrink-Optionen mit Beschreibungen
DEFAULT_OPTIONS = {
    '-a': 'Automatisch alle Fragen mit Ja beantworten',
    '-d': 'Debug-Nachrichten ausgeben',
    '-r': 'Log-Dateien entfernen',
    '-f': 'Überprüfung des freien Speicherplatzes überspringen',
    '-s': 'Autoexpand der Partition überspringen',
    '-z': 'Image nach dem Shrinken komprimieren'
}

class OutputDialog(QtWidgets.QDialog):
    append_text_signal = pyqtSignal(str)

    def __init__(self, shrink_log_path):
        super().__init__()
        self.setWindowTitle("Ausgabe des Shrink-Skripts")
        self.resize(800, 600)
        self.layout = QtWidgets.QVBoxLayout()

        # Textbereich für die Ausgabe
        self.output_text = QtWidgets.QPlainTextEdit()
        self.output_text.setReadOnly(True)
        self.layout.addWidget(self.output_text)

        # Buttons
        buttons_layout = QtWidgets.QHBoxLayout()
        self.view_shrink_log_button = QtWidgets.QPushButton("Shrink-Log anzeigen")
        self.view_shrink_log_button.clicked.connect(lambda: self.open_shrink_log(shrink_log_path))
        buttons_layout.addWidget(self.view_shrink_log_button)

        self.close_button = QtWidgets.QPushButton("Schließen")
        self.close_button.clicked.connect(self.close)
        buttons_layout.addWidget(self.close_button)

        self.layout.addLayout(buttons_layout)

        self.setLayout(self.layout)

        # Signal-Verbindungen
        self.append_text_signal.connect(self.output_text.appendPlainText)

        # Timer zum automatischen Schließen nach 5 Minuten (300 Sekunden)
        self.remaining_time = 300  # Sekunden
        self.update_close_button()
        self.auto_close_timer = QtCore.QTimer(self)
        self.auto_close_timer.setInterval(1000)  # 1 Sekunde
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
        if shrink_log_path and os.path.exists(shrink_log_path):
            try:
                # Öffne das Shrink-Log mit der Standardanwendung
                if not QDesktopServices.openUrl(QUrl.fromLocalFile(shrink_log_path)):
                    raise Exception("QDesktopServices.openUrl() konnte die Datei nicht öffnen.")
                logger.info(f"[LOGVIEWER] Öffne Shrink-Log: {shrink_log_path}")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Fehler", f"Kann Shrink-Log nicht öffnen: {e}")
                logger.error(f"[LOGVIEWER ERROR] Kann Shrink-Log nicht öffnen: {e}")
        else:
            QtWidgets.QMessageBox.information(self, "Info", "Shrink-Log-Datei nicht gefunden.")
            logger.warning("[LOGVIEWER] Shrink-Log-Datei nicht gefunden.")

    def closeEvent(self, event):
        self.auto_close_timer.stop()
        event.accept()  # Nur das Fenster schließen, nicht das gesamte Programm

class LogViewer(QtWidgets.QDialog):
    def __init__(self, main_log_filename, backup_folder, backup_pattern, delete_days=7):
        super().__init__()
        self.setWindowTitle("Log Viewer")
        self.resize(1200, 800)
        self.layout = QtWidgets.QVBoxLayout()

        self.main_log_filename = main_log_filename
        self.backup_folder = backup_folder
        self.backup_pattern = backup_pattern
        self.delete_days = delete_days  # Standardwert für das Löschen von Logs

        # Such- und Filterbereich
        filter_layout = QtWidgets.QHBoxLayout()

        # Filter für Log-Level
        self.level_filter = QtWidgets.QComboBox()
        self.level_filter.addItem("Alle Levels")
        self.level_filter.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.level_filter.currentIndexChanged.connect(self.apply_filters)
        filter_layout.addWidget(QtWidgets.QLabel("Log-Level:"))
        filter_layout.addWidget(self.level_filter)

        # Suchfeld für Nachrichten
        self.search_field = QtWidgets.QLineEdit()
        self.search_field.setPlaceholderText("Nach Nachricht suchen...")
        self.search_field.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(QtWidgets.QLabel("Suche:"))
        filter_layout.addWidget(self.search_field)

        self.layout.addLayout(filter_layout)

        # Tabbed Interface für Haupt- und Shrink-Logs
        self.tabs = QtWidgets.QTabWidget()
        self.layout.addWidget(self.tabs)

        # Hauptprozess-Log Tab
        self.main_log_tab = QtWidgets.QWidget()
        self.main_log_layout = QtWidgets.QVBoxLayout()
        self.main_log_table = QtWidgets.QTableWidget()
        self.main_log_table.setColumnCount(3)
        self.main_log_table.setHorizontalHeaderLabels(["Timestamp", "Level", "Message"])
        self.main_log_table.horizontalHeader().setStretchLastSection(True)
        self.main_log_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.main_log_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.main_log_layout.addWidget(self.main_log_table)

        # Buttons für Haupt-Log
        main_log_buttons_layout = QtWidgets.QHBoxLayout()
        self.refresh_main_log_button = QtWidgets.QPushButton('Haupt-Log aktualisieren')
        self.refresh_main_log_button.clicked.connect(lambda: self.load_logs(self.main_log_filename, self.main_log_table))
        main_log_buttons_layout.addWidget(self.refresh_main_log_button)

        self.export_main_log_button = QtWidgets.QPushButton('Log exportieren')
        self.export_main_log_button.clicked.connect(lambda: self.export_logs(self.main_log_table, "Haupt-Log"))
        main_log_buttons_layout.addWidget(self.export_main_log_button)

        self.clear_main_log_button = QtWidgets.QPushButton('Logs bis X Tage löschen')
        self.clear_main_log_button.clicked.connect(lambda: self.clear_logs(self.main_log_filename))
        main_log_buttons_layout.addWidget(self.clear_main_log_button)

        self.main_log_layout.addLayout(main_log_buttons_layout)
        self.main_log_tab.setLayout(self.main_log_layout)
        self.tabs.addTab(self.main_log_tab, "Haupt-Log")

        # Shrink-Logs Tab
        self.shrink_logs_tab = QtWidgets.QWidget()
        self.shrink_logs_layout = QtWidgets.QVBoxLayout()

        # Liste der Shrink-Logs
        self.shrink_logs_list = QtWidgets.QListWidget()
        self.shrink_logs_layout.addWidget(self.shrink_logs_list)

        # Buttons für Shrink-Logs
        shrink_logs_buttons_layout = QtWidgets.QHBoxLayout()
        self.refresh_shrink_logs_button = QtWidgets.QPushButton('Shrink-Logs aktualisieren')
        self.refresh_shrink_logs_button.clicked.connect(lambda: self.load_shrink_logs())
        shrink_logs_buttons_layout.addWidget(self.refresh_shrink_logs_button)

        self.export_shrink_logs_button = QtWidgets.QPushButton('Shrink-Logs exportieren')
        self.export_shrink_logs_button.clicked.connect(lambda: self.export_shrink_logs())
        shrink_logs_buttons_layout.addWidget(self.export_shrink_logs_button)

        self.clear_shrink_logs_button = QtWidgets.QPushButton('Shrink-Logs bis X Tage löschen')
        self.clear_shrink_logs_button.clicked.connect(lambda: self.clear_shrink_logs())
        shrink_logs_buttons_layout.addWidget(self.clear_shrink_logs_button)

        self.shrink_logs_layout.addLayout(shrink_logs_buttons_layout)

        self.shrink_logs_tab.setLayout(self.shrink_logs_layout)
        self.tabs.addTab(self.shrink_logs_tab, "Shrink-Logs")

        self.setLayout(self.layout)

        # Laden der Logs
        self.load_logs(self.main_log_filename, self.main_log_table)
        self.load_shrink_logs()

    def load_logs(self, log_filename, table_widget):
        if os.path.exists(log_filename):
            try:
                with open(log_filename, 'r') as f:
                    lines = f.readlines()
                # Sortieren der Logs mit neuesten zuerst
                lines.reverse()
                table_widget.setRowCount(0)
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    # Erwartetes Format: 'YYYY-MM-DD HH:MM:SS,mmm - LEVEL - Message'
                    try:
                        timestamp, level, message = re.split(r' - ', line, maxsplit=2)
                        row_position = table_widget.rowCount()
                        table_widget.insertRow(row_position)
                        table_widget.setItem(row_position, 0, QtWidgets.QTableWidgetItem(timestamp))
                        table_widget.setItem(row_position, 1, QtWidgets.QTableWidgetItem(level))
                        table_widget.setItem(row_position, 2, QtWidgets.QTableWidgetItem(message))
                    except ValueError:
                        # Falls das Log-Format nicht stimmt
                        logger.warning(f"[LOGVIEWER] Unbekanntes Log-Format: {line}")
                table_widget.sortItems(0, Qt.DescendingOrder)
                logger.info(f"[LOGVIEWER] Logs geladen: {log_filename}")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Fehler", f"Fehler beim Laden der Log-Datei: {e}")
                logger.error(f"[LOGVIEWER ERROR] Fehler beim Laden der Log-Datei {log_filename}: {e}")
        else:
            QtWidgets.QMessageBox.information(self, "Info", f"Log-Datei nicht gefunden: {log_filename}")
            logger.warning(f"[LOGVIEWER] Log-Datei nicht gefunden: {log_filename}")

    def load_shrink_logs(self):
        self.shrink_logs_list.clear()
        for root, dirs, files in os.walk(self.backup_folder):
            if "shrink.log" in files:
                shrink_log_path = os.path.join(root, "shrink.log")
                backup_folder_name = os.path.basename(root)
                item_text = f"{backup_folder_name} - {shrink_log_path}"
                list_item = QtWidgets.QListWidgetItem(item_text)
                self.shrink_logs_list.addItem(list_item)
        logger.debug("[LOGVIEWER] Shrink-Logs geladen.")

    def apply_filters(self):
        # Filtern der Haupt-Logs
        level = self.level_filter.currentText()
        search = self.search_field.text().lower()

        for row in range(self.main_log_table.rowCount()):
            level_item = self.main_log_table.item(row, 1)
            message_item = self.main_log_table.item(row, 2)
            level_match = (level == "Alle Levels") or (level_item.text() == level)
            search_match = (search in message_item.text().lower())
            should_show = level_match and search_match
            self.main_log_table.setRowHidden(row, not should_show)

    def export_logs(self, table_widget, log_type):
        if table_widget.rowCount() == 0:
            QtWidgets.QMessageBox.information(self, "Info", "Keine Logs zum Exportieren vorhanden.")
            return
        options = QtWidgets.QFileDialog.Options()
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, f"Exportiere {log_type}", "", "Text Files (*.txt);;All Files (*)", options=options)
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    for row in range(table_widget.rowCount()):
                        timestamp = table_widget.item(row, 0).text()
                        level = table_widget.item(row, 1).text()
                        message = table_widget.item(row, 2).text()
                        f.write(f"{timestamp} - {level} - {message}\n")
                QtWidgets.QMessageBox.information(self, "Erfolg", f"{log_type} erfolgreich exportiert.")
                logger.info(f"[LOGVIEWER] {log_type} exportiert nach {file_path}")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Fehler", f"Fehler beim Exportieren der Logs: {e}")
                logger.error(f"[LOGVIEWER ERROR] Fehler beim Exportieren der Logs nach {file_path}: {e}")

    def export_shrink_logs(self):
        if self.shrink_logs_list.count() == 0:
            QtWidgets.QMessageBox.information(self, "Info", "Keine Shrink-Logs zum Exportieren vorhanden.")
            return
        options = QtWidgets.QFileDialog.Options()
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Exportiere Shrink-Logs", "", "Text Files (*.txt);;All Files (*)", options=options)
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    for index in range(self.shrink_logs_list.count()):
                        item = self.shrink_logs_list.item(index)
                        f.write(f"{item.text()}\n")
                QtWidgets.QMessageBox.information(self, "Erfolg", "Shrink-Logs erfolgreich exportiert.")
                logger.info(f"[LOGVIEWER] Shrink-Logs exportiert nach {file_path}")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Fehler", f"Fehler beim Exportieren der Shrink-Logs: {e}")
                logger.error(f"[LOGVIEWER ERROR] Fehler beim Exportieren der Shrink-Logs nach {file_path}: {e}")

    def clear_logs(self, log_filename):
        days, ok = QtWidgets.QInputDialog.getInt(self, "Logs löschen", "Logs löschen bis zu wie vielen Tagen?", value=self.delete_days, min=1, max=3650)
        if ok:
            cutoff_time = datetime.datetime.now() - datetime.timedelta(days=days)
            try:
                with open(log_filename, 'r') as f:
                    lines = f.readlines()
                with open(log_filename, 'w') as f:
                    for line in lines:
                        try:
                            timestamp_str, level, message = re.split(r' - ', line, maxsplit=2)
                            timestamp = datetime.datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
                            if timestamp >= cutoff_time:
                                f.write(line)
                        except ValueError:
                            # Unbekanntes Format, behalten wir die Zeile
                            f.write(line)
                QtWidgets.QMessageBox.information(self, "Erfolg", f"Logs bis zu {days} Tagen wurden gelöscht.")
                logger.info(f"[LOGVIEWER] Logs bis zu {days} Tagen in {log_filename} gelöscht.")
                self.load_logs(log_filename, self.main_log_table)
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Fehler", f"Fehler beim Löschen der Logs: {e}")
                logger.error(f"[LOGVIEWER ERROR] Fehler beim Löschen der Logs in {log_filename}: {e}")

    def clear_shrink_logs(self):
        days, ok = QtWidgets.QInputDialog.getInt(self, "Shrink-Logs löschen", "Shrink-Logs löschen bis zu wie vielen Tagen?", value=self.delete_days, min=1, max=3650)
        if ok:
            cutoff_time = datetime.datetime.now() - datetime.timedelta(days=days)
            try:
                for index in range(self.shrink_logs_list.count()):
                    item = self.shrink_logs_list.item(index)
                    try:
                        backup_folder_name, shrink_log_path = item.text().split(" - ", maxsplit=1)
                    except ValueError:
                        logger.warning(f"[LOGVIEWER] Unerwartetes Shrink-Log-Format: {item.text()}")
                        continue
                    if os.path.exists(shrink_log_path):
                        with open(shrink_log_path, 'r') as f:
                            lines = f.readlines()
                        with open(shrink_log_path, 'w') as f:
                            for line in lines:
                                try:
                                    timestamp_str, level, message = re.split(r' - ', line, maxsplit=2)
                                    timestamp = datetime.datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
                                    if timestamp >= cutoff_time:
                                        f.write(line)
                                except ValueError:
                                    # Unbekanntes Format, behalten wir die Zeile
                                    f.write(line)
                        logger.info(f"[LOGVIEWER] Shrink-Log bis zu {days} Tagen in {shrink_log_path} gelöscht.")
                QtWidgets.QMessageBox.information(self, "Erfolg", f"Shrink-Logs bis zu {days} Tagen wurden gelöscht.")
                self.load_shrink_logs()
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Fehler", f"Fehler beim Löschen der Shrink-Logs: {e}")
                logger.error(f"[LOGVIEWER ERROR] Fehler beim Löschen der Shrink-Logs: {e}")

class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, settings_file):
        super().__init__()
        self.setWindowTitle('Einstellungen')
        self.setFixedSize(400, 200)
        self.settings_file = settings_file
        layout = QtWidgets.QVBoxLayout()

        # Ältere Backups löschen
        delete_backups_layout = QtWidgets.QHBoxLayout()
        self.delete_backups_switch = QtWidgets.QCheckBox("Ältere Backups löschen")
        delete_backups_layout.addWidget(self.delete_backups_switch)
        self.hours_input = QtWidgets.QSpinBox()
        self.hours_input.setRange(1, 5000)
        delete_backups_layout.addWidget(self.hours_input)
        hours_label = QtWidgets.QLabel("Stunden")
        delete_backups_layout.addWidget(hours_label)
        layout.addLayout(delete_backups_layout)

        # Logging Optionen
        logging_layout = QtWidgets.QHBoxLayout()
        self.logging_switch = QtWidgets.QCheckBox("Log-Datei erstellen")
        logging_layout.addWidget(self.logging_switch)
        self.advanced_logging_checkbox = QtWidgets.QCheckBox("Erweitertes Log")
        logging_layout.addWidget(self.advanced_logging_checkbox)
        layout.addLayout(logging_layout)

        # Buttons
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
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
            QtWidgets.QMessageBox.information(self, 'Einstellungen', 'Einstellungen gespeichert.')
            logger.info("[SETTINGS] Einstellungen gespeichert.")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Fehler', f'Einstellungen konnten nicht gespeichert werden: {e}')
            logger.error(f"[ERROR] Einstellungen konnten nicht gespeichert werden: {e}")

    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                self.logging_switch.setChecked(settings.get('logging_enabled', False))
                self.advanced_logging_checkbox.setChecked(settings.get('advanced_logging', False))
                self.delete_backups_switch.setChecked(settings.get('delete_backups', False))
                self.hours_input.setValue(settings.get('delete_hours', 168))
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, 'Fehler', f'Einstellungen konnten nicht geladen werden: {e}')
                logger.error(f"[ERROR] Einstellungen konnten nicht geladen werden: {e}")

class ShrinkGUI(QtWidgets.QWidget):
    def __init__(self, img_path, settings_file):
        super().__init__()
        self.img_path = img_path
        self.settings_file = settings_file
        self.timer = QtCore.QTimer(self)
        self.time_left = 60  # Sekunden bis zum automatischen Start
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Shrink-Optionen')
        self.setFixedSize(600, 400)

        layout = QtWidgets.QVBoxLayout()

        # Befehlsanzeige (editierbar)
        command_label = QtWidgets.QLabel('Auszuführender Befehl:')
        layout.addWidget(command_label)
        self.command_edit = QtWidgets.QLineEdit()
        self.command_edit.setReadOnly(False)  # Editierbar machen
        layout.addWidget(self.command_edit)

        # PiShrink-Optionen
        self.option_checks = {}
        options_layout = QtWidgets.QHBoxLayout()
        for opt, desc in DEFAULT_OPTIONS.items():
            checkbox = QtWidgets.QCheckBox(opt)
            checkbox.setToolTip(desc)
            checkbox.stateChanged.connect(self.update_command)
            options_layout.addWidget(checkbox)
            self.option_checks[opt] = checkbox
        layout.addLayout(options_layout)

        # Optionale Einstellungen
        options_layout = QtWidgets.QHBoxLayout()

        # Logging Optionen
        self.logging_switch = QtWidgets.QCheckBox("Log-Datei erstellen")
        options_layout.addWidget(self.logging_switch)

        self.advanced_logging_checkbox = QtWidgets.QCheckBox("Erweitertes Log")
        options_layout.addWidget(self.advanced_logging_checkbox)

        options_layout.addStretch()

        # Ältere Backups löschen
        self.delete_backups_switch = QtWidgets.QCheckBox("Ältere Backups löschen")
        options_layout.addWidget(self.delete_backups_switch)

        self.hours_input = QtWidgets.QSpinBox()
        self.hours_input.setRange(1, 5000)  # Erhöhtes Maximum
        self.hours_input.setValue(168)  # Standardwert
        options_layout.addWidget(self.hours_input)

        hours_label = QtWidgets.QLabel("Stunden")
        options_layout.addWidget(hours_label)

        layout.addLayout(options_layout)

        # Timer und Speicherplatz Anzeige
        timer_layout = QtWidgets.QHBoxLayout()
        self.timer_label = QtWidgets.QLabel(f"Automatischer Start in {self.time_left} Sekunden")
        timer_layout.addWidget(self.timer_label)

        timer_layout.addStretch()

        self.space_label = QtWidgets.QLabel()
        timer_layout.addWidget(self.space_label)

        layout.addLayout(timer_layout)

        # Buttons
        buttons_layout = QtWidgets.QHBoxLayout()
        self.save_button = QtWidgets.QPushButton('Einstellungen speichern')
        self.save_button.clicked.connect(self.save_settings)
        buttons_layout.addWidget(self.save_button)

        self.run_button = QtWidgets.QPushButton('Befehl ausführen')
        self.run_button.clicked.connect(self.run_command)
        buttons_layout.addWidget(self.run_button)

        layout.addLayout(buttons_layout)
        self.setLayout(layout)

        # Gespeicherte Einstellungen laden
        self.load_settings()

        # Timer starten
        self.timer.timeout.connect(self.update_timer)
        self.timer.start(1000)  # Jede Sekunde

        # Initiale Aktualisierung des Speicherplatzes
        self.update_space_label()

        # Initiale Aktualisierung des Befehls
        self.update_command()

    def update_command(self):
        # Stellen Sie sicher, dass PISHRINK_SCRIPT korrekt definiert ist
        PISHRINK_SCRIPT = "/home/raphi/pythonScripts/auto_dd_shrinker/pishrink.sh"
        if not os.path.exists(PISHRINK_SCRIPT):
            logger.error(f"PiShrink-Skript nicht gefunden: {PISHRINK_SCRIPT}")
            QtWidgets.QMessageBox.critical(self, "Fehler", f"PiShrink-Skript nicht gefunden:\n{PISHRINK_SCRIPT}")
            self.run_button.setEnabled(False)
            return
        else:
            self.run_button.setEnabled(True)
        options = ' '.join([opt for opt, cb in self.option_checks.items() if cb.isChecked()])
        command = f'sudo bash "{PISHRINK_SCRIPT}" {options} "{self.img_path}"'
        self.command_edit.setText(command)

    def save_settings(self):
        settings = {
            'logging_enabled': self.logging_switch.isChecked(),
            'advanced_logging': self.advanced_logging_checkbox.isChecked(),
            'delete_backups': self.delete_backups_switch.isChecked(),
            'delete_hours': self.hours_input.value()
        }
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
            QtWidgets.QMessageBox.information(self, 'Einstellungen', 'Einstellungen gespeichert.')
            logger.info("[SETTINGS] Einstellungen gespeichert.")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Fehler', f'Einstellungen konnten nicht gespeichert werden: {e}')
            logger.error(f"[ERROR] Einstellungen konnten nicht gespeichert werden: {e}")

    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                self.logging_switch.setChecked(settings.get('logging_enabled', False))
                self.advanced_logging_checkbox.setChecked(settings.get('advanced_logging', False))
                self.delete_backups_switch.setChecked(settings.get('delete_backups', False))
                self.hours_input.setValue(settings.get('delete_hours', 168))
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, 'Fehler', f'Einstellungen konnten nicht geladen werden: {e}')
                logger.error(f"[ERROR] Einstellungen konnten nicht geladen werden: {e}")
        self.update_command()

    def update_timer(self):
        self.time_left -= 1
        self.timer_label.setText(f"Automatischer Start in {self.time_left} Sekunden")
        if self.time_left <= 0:
            self.run_command()

    def update_space_label(self):
        try:
            # Hier setzen Sie den Pfad zu einer Datei oder einem Verzeichnis, um den Speicherplatz abzurufen
            # Beispiel: Verwenden Sie das Backup-Verzeichnis
            statvfs = os.statvfs(os.path.dirname(self.img_path))
            free = statvfs.f_bavail * statvfs.f_frsize
            free_gb = free / (2**30)  # In GB umwandeln
            self.space_label.setText(f"Freier Speicherplatz: {free_gb:.2f} GB")
            logger.debug(f"[SPACE] Freier Speicherplatz: {free_gb:.2f} GB")
        except Exception as e:
            self.space_label.setText("Speicherplatz: N/A")
            logger.error(f"[ERROR] Konnte Speicherplatz nicht abrufen: {e}")

    def run_command(self):
        command = self.command_edit.text()
        if not command:
            QtWidgets.QMessageBox.warning(self, "Warnung", "Kein Befehl zum Ausführen vorhanden.")
            return
        logger.info(f"[SHRINK] Ausführen des Befehls: {command}")
        
        # Shrink-Log-Pfad für den OutputDialog
        shrink_log_path = os.path.join(os.path.dirname(self.img_path), "shrink.log") if self.logging_switch.isChecked() else None

        # Shrink-Log-Dialog erstellen, falls Logging aktiviert ist
        if shrink_log_path:
            self.output_dialog = OutputDialog(shrink_log_path)
            self.output_dialog.show()
            logger.debug("OutputDialog für Shrink-Prozess erstellt.")
        else:
            self.output_dialog = None

        # Starten des Shrink-Prozesses in einem separaten Thread
        threading.Thread(target=self.run_process, args=(command, shrink_log_path), daemon=True).start()

        self.timer.stop()
        self.close()  # GUI schließen, Programm läuft weiter

    def run_process(self, command, shrink_log_path):
        try:
            logger.info(f"[SHRINK] Startet Shrink-Prozess: {command}")
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in process.stdout:
                line = line.strip()
                print(line)
                if self.output_dialog:
                    self.output_dialog.append_output(line)
                logger.info(f"[SHRINK OUTPUT] {line}")
            process.wait()
            if self.output_dialog:
                self.output_dialog.append_output("\nBefehl abgeschlossen.")
            logger.info(f"[SHRINK] Shrink-Prozess abgeschlossen: {command}")
            self.post_process()
        except Exception as e:
            error_message = f"Fehler beim Ausführen des Befehls: {e}"
            print(f"[ERROR] {error_message}")
            if self.output_dialog:
                self.output_dialog.append_output(f"[ERROR] {error_message}")
            logger.error(f"[ERROR] {error_message}")
            self.show_error_dialog(error_message)

    def show_error_dialog(self, error_message):
        self.error_dialog = QtWidgets.QMessageBox()
        self.error_dialog.setIcon(QtWidgets.QMessageBox.Warning)
        self.error_dialog.setWindowTitle("Fehler")
        self.error_dialog.setText("Ein Fehler ist aufgetreten:")
        self.error_dialog.setInformativeText(error_message)
        self.error_dialog.setStandardButtons(QtWidgets.QMessageBox.Ok)
        self.error_dialog.show()  # Fenster bleibt offen
        logger.error(f"[ERROR] {error_message}")

    def post_process(self):
        # Löschen alter Backups, falls aktiviert
        if self.delete_backups_switch.isChecked():
            hours = self.hours_input.value()
            logger.info(f"[DELETE] Lösche Backups älter als {hours} Stunden")
            self.delete_old_backups(hours)
        else:
            logger.info("[DELETE] Löschfunktion nicht aktiviert.")

    def delete_old_backups(self, hours):
        backup_dir = os.path.dirname(os.path.dirname(self.img_path))
        logger.debug(f"[DELETE] Backup-Verzeichnis: {backup_dir}")
        cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=hours)
        backups_found = False  # Flag, um zu überprüfen, ob Backups gefunden wurden
        try:
            for item in os.listdir(backup_dir):
                item_path = os.path.join(backup_dir, item)
                if os.path.isdir(item_path):
                    folder_name = os.path.basename(item_path)
                    logger.debug(f"[DELETE] Überprüfe Ordner: {folder_name}")
                    if item_path == os.path.dirname(self.img_path):
                        logger.debug(f"[DELETE] Überspringe aktuelles Backup: {item_path}")
                        continue  # Überspringen des aktuellen Backups
                    match = re.match(r"raspihaupt-dd-backup-(\d{8})-(\d{6})", folder_name)
                    if match:
                        date_str = match.group(1)  # YYYYMMDD
                        time_str = match.group(2)  # HHMMSS
                        folder_datetime_str = date_str + time_str  # 'YYYYMMDDHHMMSS'
                        try:
                            folder_datetime = datetime.datetime.strptime(folder_datetime_str, '%Y%m%d%H%M%S')
                            logger.debug(f"[DELETE] Ordnerzeit: {folder_datetime}, Grenzzeit: {cutoff_time}")
                            if folder_datetime < cutoff_time:
                                backups_found = True
                                try:
                                    shutil.rmtree(item_path)
                                    logger.info(f"[DELETE] Altes Backup gelöscht: {item_path}")
                                except Exception as e:
                                    error_message = f"Konnte {item_path} nicht löschen: {e}"
                                    logger.error(f"[ERROR] {error_message}")
                                    self.show_error_dialog(error_message)
                        except ValueError as ve:
                            logger.error(f"[ERROR] Ungültiges Datum/Uhrzeit im Ordnernamen {folder_name}: {ve}")
                    else:
                        logger.debug(f"[DELETE] Ordner {folder_name} entspricht nicht dem Muster und wird übersprungen.")
            if not backups_found:
                logger.info("[DELETE] Keine alten Backups zum Löschen gefunden.")
            else:
                logger.info("[DELETE] Löschvorgang abgeschlossen.")
        except Exception as e:
            error_message = f"Fehler beim Löschen alter Backups: {e}"
            logger.error(f"[ERROR] {error_message}")
            self.show_error_dialog(error_message)
