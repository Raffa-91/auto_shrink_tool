#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import time
import threading
import subprocess
import shutil
import logging
import json
import re
import datetime
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# =======================
# Konfigurationsvariablen
# =======================

BACKUP_FOLDER = "/media/raphi/hdd/backups/raspiHauptDD/raspihaupt"  # Pfad zum überwachten Backup-Ordner
PISHRINK_SCRIPT = "/home/raphi/pythonScripts/auto_dd_shrinker/pishrink.sh"  # Pfad zum PiShrink-Skript
ICON_PATH = "/home/raphi/pythonScripts/auto_dd_shrinker/icon.png"  # Pfad zum Tray-Icon
SETTINGS_FILE = "settings.json"  # Pfad zur Einstellungsdatei

# Muster für Backup-Ordner (Passen Sie das Muster ggf. an Ihre Ordnernamen an)
BACKUP_FOLDER_PATTERN = r"raspihaupt-dd-backup-(\d{8})-(\d{6})"

# PiShrink-Optionen mit Beschreibungen
DEFAULT_OPTIONS = {
    '-a': 'Automatisch alle Fragen mit Ja beantworten',
    '-d': 'Debug-Nachrichten ausgeben',
    '-r': 'Log-Dateien entfernen',
    '-f': 'Überprüfung des freien Speicherplatzes überspringen',
    '-s': 'Autoexpand der Partition überspringen',
    '-z': 'Image nach dem Shrinken komprimieren'
}

# Gespeicherte Einstellungen mit Standardwerten
saved_settings = {
    'options': [],
    'logging_enabled': False,
    'advanced_logging': False,
    'delete_backups': False,
    'delete_hours': 168  # Standardmäßig 168 Stunden (7 Tage)
}

# ===================
# Logging-Konfiguration
# ===================

# Hauptprozess-Logger
main_logger = logging.getLogger('AutoDDShrinker_Main')
main_logger.setLevel(logging.DEBUG)  # Set to DEBUG for detailed logs

# Formatter für den Hauptprozess-Logger
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# FileHandler für den Hauptprozess-Logger
main_log_filename = "autodds_monitor.log"
main_file_handler = logging.FileHandler(main_log_filename)
main_file_handler.setFormatter(formatter)
main_logger.addHandler(main_file_handler)

# StreamHandler für die Konsolenausgabe
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
main_logger.addHandler(console_handler)

# ======================
# Worker Signals
# ======================

class WorkerSignals(QtCore.QObject):
    new_image = QtCore.pyqtSignal(str)
    error_occurred = QtCore.pyqtSignal(str)

# ======================
# Backup Event Handler
# ======================

class BackupEventHandler(FileSystemEventHandler):
    def __init__(self, signals):
        super().__init__()
        self.signals = signals
        self.monitored_folders = set()

    def on_created(self, event):
        self.process_event(event)

    def on_modified(self, event):
        self.process_event(event)

    def process_event(self, event):
        main_logger.debug(f"[EVENT] Event erkannt: {event.src_path}")
        try:
            if event.is_directory:
                folder_name = os.path.basename(event.src_path)
                if re.match(BACKUP_FOLDER_PATTERN, folder_name):
                    if event.src_path not in self.monitored_folders:
                        main_logger.info(f"[SCAN] Neuer Backup-Ordner erkannt: {event.src_path}")
                        self.monitored_folders.add(event.src_path)
                        threading.Thread(target=self.monitor_new_folder, args=(event.src_path,), daemon=True).start()
            else:
                # Prüfen, ob raspiBackup.log erstellt wurde
                if os.path.basename(event.src_path) == "raspiBackup.log":
                    folder_path = os.path.dirname(event.src_path)
                    if folder_path not in self.monitored_folders:
                        folder_name = os.path.basename(folder_path)
                        if re.match(BACKUP_FOLDER_PATTERN, folder_name):
                            main_logger.info(f"[SCAN] raspiBackup.log in neuem Ordner gefunden: {folder_path}")
                            self.monitored_folders.add(folder_path)
                            threading.Thread(target=self.monitor_new_folder, args=(folder_path,), daemon=True).start()
        except Exception as e:
            error_message = f"Fehler bei der Verarbeitung des Ereignisses {event.src_path}: {e}"
            main_logger.error(f"[ERROR] {error_message}")
            self.signals.error_occurred.emit(error_message)

    def monitor_new_folder(self, folder_path):
        main_logger.debug(f"[MONITOR] Überwache neuen Ordner auf raspiBackup.log: {folder_path}")
        log_file_path = os.path.join(folder_path, "raspiBackup.log")
        try:
            while True:
                if os.path.exists(log_file_path):
                    main_logger.info(f"[FOUND] raspiBackup.log gefunden: {log_file_path}")
                    time.sleep(10)  # Warten, bis das Log-File vollständig geschrieben ist
                    img_files = [f for f in os.listdir(folder_path) if f.endswith('.img')]
                    if img_files:
                        for img_file in img_files:
                            img_path = os.path.join(folder_path, img_file)
                            self.signals.new_image.emit(img_path)
                        break
                    else:
                        main_logger.warning(f"[WARNING] Keine .img-Datei im Ordner gefunden: {folder_path}")
                        break
                else:
                    time.sleep(5)
        except Exception as e:
            error_message = f"Fehler beim Überwachen des Ordners {folder_path}: {e}"
            main_logger.error(f"[ERROR] {error_message}")
            self.signals.error_occurred.emit(error_message)

# ======================
# Output Dialog
# ======================

class OutputDialog(QtWidgets.QDialog):
    append_text_signal = QtCore.pyqtSignal(str)

    def __init__(self, shrink_log_path):
        super().__init__()
        self.setWindowTitle("Ausgabe des Shrink-Skripts")
        self.resize(800, 600)
        self.layout = QtWidgets.QVBoxLayout()

        # Textbereich für die Ausgabe
        self.output_text = QtWidgets.QPlainTextEdit()
        self.output_text.setReadOnly(True)
        self.layout.addWidget(self.output_text)

        # Button zum Schließen mit Countdown
        self.close_button = QtWidgets.QPushButton()
        self.close_button.clicked.connect(self.close)
        self.layout.addWidget(self.close_button)

        # Button zum Öffnen des Shrink-Logs
        self.view_shrink_log_button = QtWidgets.QPushButton("Shrink-Log anzeigen")
        self.view_shrink_log_button.clicked.connect(lambda: self.open_shrink_log(shrink_log_path))
        self.layout.addWidget(self.view_shrink_log_button)

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
        if os.path.exists(shrink_log_path):
            try:
                # Öffne das Shrink-Log mit dem Standard-Texteditor
                QDesktopServices.openUrl(QUrl.fromLocalFile(shrink_log_path))
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

# ======================
# Shrink GUI
# ======================

class ShrinkGUI(QtWidgets.QWidget):
    def __init__(self, img_path):
        super().__init__()
        self.img_path = img_path
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
        self.hours_input.setValue(saved_settings.get('delete_hours', 168))
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
        options = ' '.join([opt for opt, cb in self.option_checks.items() if cb.isChecked()])
        command = f'sudo bash "{PISHRINK_SCRIPT}" {options} "{self.img_path}"'
        self.command_edit.setText(command)

    def save_settings(self):
        saved_settings['options'] = [opt for opt, cb in self.option_checks.items() if cb.isChecked()]
        saved_settings['logging_enabled'] = self.logging_switch.isChecked()
        saved_settings['advanced_logging'] = self.advanced_logging_checkbox.isChecked()
        saved_settings['delete_backups'] = self.delete_backups_switch.isChecked()
        saved_settings['delete_hours'] = self.hours_input.value()
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(saved_settings, f)
        QtWidgets.QMessageBox.information(self, 'Einstellungen', 'Einstellungen gespeichert.')
        main_logger.info("[SETTINGS] Einstellungen gespeichert.")

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                global saved_settings
                saved_settings = json.load(f)
        # Optionen laden
        for opt, cb in self.option_checks.items():
            cb.setChecked(opt in saved_settings.get('options', []))
        # Sonstige Einstellungen laden
        self.logging_switch.setChecked(saved_settings.get('logging_enabled', False))
        self.advanced_logging_checkbox.setChecked(saved_settings.get('advanced_logging', False))
        self.delete_backups_switch.setChecked(saved_settings.get('delete_backups', False))
        self.hours_input.setValue(saved_settings.get('delete_hours', 168))
        self.update_command()

    def update_timer(self):
        self.time_left -= 1
        self.timer_label.setText(f"Automatischer Start in {self.time_left} Sekunden")
        if self.time_left <= 0:
            self.run_command()

    def update_space_label(self):
        try:
            statvfs = os.statvfs(self.img_path)
            free = statvfs.f_bavail * statvfs.f_frsize
            free_gb = free / (2**30)  # In GB umwandeln
            self.space_label.setText(f"Freier Speicherplatz: {free_gb:.2f} GB")
            main_logger.debug(f"[SPACE] Freier Speicherplatz: {free_gb:.2f} GB")
        except Exception as e:
            self.space_label.setText("Speicherplatz: N/A")
            main_logger.error(f"[ERROR] Konnte Speicherplatz nicht abrufen: {e}")

    def run_command(self):
        command = self.command_edit.text()
        main_logger.info(f"[SHRINK] Ausführen des Befehls: {command}")
        # Logging einrichten, falls aktiviert
        if self.logging_switch.isChecked():
            shrink_log_path = os.path.join(os.path.dirname(self.img_path), "shrink.log")
            shrink_logger = logging.getLogger(f'Shrink_{os.path.basename(self.img_path)}')
            shrink_logger.setLevel(logging.DEBUG if self.advanced_logging_checkbox.isChecked() else logging.INFO)
            shrink_file_handler = logging.FileHandler(shrink_log_path)
            shrink_file_handler.setFormatter(formatter)
            # Entfernen vorheriger Handler
            if shrink_logger.hasHandlers():
                shrink_logger.handlers.clear()
            shrink_logger.addHandler(shrink_file_handler)
        else:
            shrink_logger = None

        # Shrink-Log-Pfad für den OutputDialog
        shrink_log_path = os.path.join(os.path.dirname(self.img_path), "shrink.log")

        # Shrink-Log-Dialog erstellen
        self.output_dialog = OutputDialog(shrink_log_path)
        self.output_dialog.show()

        # Starten des Shrink-Prozesses in einem separaten Thread
        threading.Thread(target=self.run_process, args=(command, shrink_logger, shrink_log_path), daemon=True).start()

        self.timer.stop()
        self.close()  # GUI schließen, Programm läuft weiter

    def run_process(self, command, shrink_logger, shrink_log_path):
        try:
            main_logger.info(f"[SHRINK] Startet Shrink-Prozess: {command}")
            process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in process.stdout:
                line = line.strip()
                print(line)
                self.output_dialog.append_output(line)
                if shrink_logger:
                    shrink_logger.info(line)
            process.wait()
            self.output_dialog.append_output("\nBefehl abgeschlossen.")
            main_logger.info(f"[SHRINK] Shrink-Prozess abgeschlossen: {command}")
            if shrink_logger:
                shrink_logger.info("Shrink-Prozess abgeschlossen.")
            self.post_process()
        except Exception as e:
            error_message = f"Fehler beim Ausführen des Befehls: {e}"
            print(f"[ERROR] {error_message}")
            self.output_dialog.append_output(f"[ERROR] {error_message}")
            main_logger.error(f"[ERROR] {error_message}")
            self.show_error_dialog(error_message)

    def show_error_dialog(self, error_message):
        self.error_dialog = QtWidgets.QMessageBox()
        self.error_dialog.setIcon(QtWidgets.QMessageBox.Warning)
        self.error_dialog.setWindowTitle("Fehler")
        self.error_dialog.setText("Ein Fehler ist aufgetreten:")
        self.error_dialog.setInformativeText(error_message)
        self.error_dialog.setStandardButtons(QtWidgets.QMessageBox.Ok)
        self.error_dialog.show()  # Fenster bleibt offen
        main_logger.error(f"[ERROR] {error_message}")

    def post_process(self):
        # Löschen alter Backups, falls aktiviert
        if self.delete_backups_switch.isChecked():
            hours = self.hours_input.value()
            main_logger.info(f"[DELETE] Lösche Backups älter als {hours} Stunden")
            self.delete_old_backups(hours)
        else:
            main_logger.info("[DELETE] Löschfunktion nicht aktiviert.")

    def delete_old_backups(self, hours):
        backup_dir = os.path.dirname(os.path.dirname(self.img_path))
        main_logger.debug(f"[DELETE] Backup-Verzeichnis: {backup_dir}")
        cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=hours)
        backups_found = False  # Flag, um zu überprüfen, ob Backups gefunden wurden
        for item in os.listdir(backup_dir):
            item_path = os.path.join(backup_dir, item)
            if os.path.isdir(item_path):
                folder_name = os.path.basename(item_path)
                main_logger.debug(f"[DELETE] Überprüfe Ordner: {folder_name}")
                if item_path == os.path.dirname(self.img_path):
                    main_logger.debug(f"[DELETE] Überspringe aktuelles Backup: {item_path}")
                    continue  # Überspringen des aktuellen Backups
                match = re.match(BACKUP_FOLDER_PATTERN, folder_name)
                if match:
                    date_str = match.group(1)  # YYYYMMDD
                    time_str = match.group(2)  # HHMMSS
                    folder_datetime_str = date_str + time_str  # 'YYYYMMDDHHMMSS'
                    try:
                        folder_datetime = datetime.datetime.strptime(folder_datetime_str, '%Y%m%d%H%M%S')
                        main_logger.debug(f"[DELETE] Ordnerzeit: {folder_datetime}, Grenzzeit: {cutoff_time}")
                        if folder_datetime < cutoff_time:
                            backups_found = True
                            try:
                                shutil.rmtree(item_path)
                                main_logger.info(f"[DELETE] Altes Backup gelöscht: {item_path}")
                            except Exception as e:
                                error_message = f"Konnte {item_path} nicht löschen: {e}"
                                main_logger.error(f"[ERROR] {error_message}")
                                self.show_error_dialog(error_message)
                    except ValueError as ve:
                        main_logger.error(f"[ERROR] Ungültiges Datum/Uhrzeit im Ordnernamen {folder_name}: {ve}")
                else:
                    main_logger.debug(f"[DELETE] Ordner {folder_name} entspricht nicht dem Muster und wird übersprungen.")
        if not backups_found:
            main_logger.info("[DELETE] Keine alten Backups zum Löschen gefunden.")
        else:
            main_logger.info("[DELETE] Löschvorgang abgeschlossen.")

# ======================
# Settings Dialog
# ======================

class SettingsDialog(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Einstellungen')
        self.setFixedSize(400, 200)
        layout = QtWidgets.QVBoxLayout()

        # Ältere Backups löschen
        delete_backups_layout = QtWidgets.QHBoxLayout()
        self.delete_backups_switch = QtWidgets.QCheckBox("Ältere Backups löschen")
        delete_backups_layout.addWidget(self.delete_backups_switch)
        self.hours_input = QtWidgets.QSpinBox()
        self.hours_input.setRange(1, 5000)
        self.hours_input.setValue(saved_settings.get('delete_hours', 168))
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
        saved_settings['logging_enabled'] = self.logging_switch.isChecked()
        saved_settings['advanced_logging'] = self.advanced_logging_checkbox.isChecked()
        saved_settings['delete_backups'] = self.delete_backups_switch.isChecked()
        saved_settings['delete_hours'] = self.hours_input.value()
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(saved_settings, f)
        QtWidgets.QMessageBox.information(self, 'Einstellungen', 'Einstellungen gespeichert.')
        main_logger.info("[SETTINGS] Einstellungen über den SettingsDialog gespeichert.")

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                global saved_settings
                saved_settings = json.load(f)
        self.logging_switch.setChecked(saved_settings.get('logging_enabled', False))
        self.advanced_logging_checkbox.setChecked(saved_settings.get('advanced_logging', False))
        self.delete_backups_switch.setChecked(saved_settings.get('delete_backups', False))
        self.hours_input.setValue(saved_settings.get('delete_hours', 168))

# ======================
# Log Viewer Dialog
# ======================

class LogViewer(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Log Viewer")
        self.resize(1000, 700)
        self.layout = QtWidgets.QVBoxLayout()

        # Tabbed Interface für Haupt- und Shrink-Logs
        self.tabs = QtWidgets.QTabWidget()
        self.layout.addWidget(self.tabs)

        # Hauptprozess-Log Tab
        self.main_log_tab = QtWidgets.QWidget()
        self.main_log_layout = QtWidgets.QVBoxLayout()
        self.main_log_text = QtWidgets.QPlainTextEdit()
        self.main_log_text.setReadOnly(True)
        self.main_log_layout.addWidget(self.main_log_text)

        # Button zum Aktualisieren des Haupt-Logs
        self.refresh_main_log_button = QtWidgets.QPushButton('Haupt-Log aktualisieren')
        self.refresh_main_log_button.clicked.connect(self.load_main_logs)
        self.main_log_layout.addWidget(self.refresh_main_log_button)

        self.main_log_tab.setLayout(self.main_log_layout)
        self.tabs.addTab(self.main_log_tab, "Haupt-Log")

        # Shrink-Logs Tab
        self.shrink_logs_tab = QtWidgets.QWidget()
        self.shrink_logs_layout = QtWidgets.QVBoxLayout()

        # Liste der Shrink-Logs
        self.shrink_logs_list = QtWidgets.QListWidget()
        self.shrink_logs_layout.addWidget(self.shrink_logs_list)

        # Button zum Aktualisieren der Shrink-Logs
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
                # Korrekte Bindung des shrink_log_path zu jedem Button
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
                # Öffne das Shrink-Log mit dem Standard-Texteditor
                QDesktopServices.openUrl(QUrl.fromLocalFile(shrink_log_path))
                main_logger.info(f"[LOGVIEWER] Öffne Shrink-Log: {shrink_log_path}")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Fehler", f"Kann Shrink-Log nicht öffnen: {e}")
                main_logger.error(f"[LOGVIEWER ERROR] Kann Shrink-Log nicht öffnen: {e}")
        else:
            QtWidgets.QMessageBox.information(self, "Info", "Shrink-Log-Datei nicht gefunden.")
            main_logger.warning("[LOGVIEWER] Shrink-Log-Datei nicht gefunden.")

# ======================
# System Tray Icon
# ======================

class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
    def __init__(self, icon_path, parent=None):
        super().__init__(QtGui.QIcon(icon_path), parent)
        self.setToolTip('Auto DD Shrinker')
        self.menu = QtWidgets.QMenu(parent)

        # Menüeinträge
        status_action = self.menu.addAction('Shrink-Skript Status anzeigen')
        status_action.triggered.connect(self.show_status)

        logs_action = self.menu.addAction('Logs anzeigen')
        logs_action.triggered.connect(self.show_logs)

        settings_action = self.menu.addAction('Einstellungen öffnen')
        settings_action.triggered.connect(self.open_settings)

        quit_action = self.menu.addAction('Beenden')
        quit_action.triggered.connect(QtWidgets.qApp.quit)

        self.setContextMenu(self.menu)

    def show_status(self):
        QtWidgets.QMessageBox.information(None, 'Status', 'Das Shrink-Skript ist aktiv.')
        main_logger.debug("[TRAY] Status angezeigt.")

    def show_logs(self):
        self.log_viewer = LogViewer()
        self.log_viewer.show()
        main_logger.debug("[TRAY] Log Viewer geöffnet.")

    def open_settings(self):
        self.settings_dialog = SettingsDialog()
        self.settings_dialog.show()
        main_logger.debug("[TRAY] SettingsDialog geöffnet.")

# ======================
# Main Application
# ======================

class MainApp(QtWidgets.QApplication):
    def __init__(self, sys_argv):
        super().__init__(sys_argv)

        # Verhindern, dass die Anwendung beendet wird, wenn das letzte Fenster geschlossen wird
        self.setQuitOnLastWindowClosed(False)

        # Tray-Icon
        self.tray_icon = SystemTrayIcon(ICON_PATH)
        self.tray_icon.show()
        main_logger.debug("[MAIN] Tray-Icon gestartet.")

        # Signale
        self.signals = WorkerSignals()
        self.signals.new_image.connect(self.show_gui)
        self.signals.error_occurred.connect(self.show_error_dialog)

        # Überwachung in separatem Thread starten
        self.monitoring_thread = threading.Thread(target=self.start_monitoring, daemon=True)
        self.monitoring_thread.start()
        main_logger.debug("[MAIN] Überwachungsthread gestartet.")

        # Verwaltung von GUI-Instanzen
        self.guis = []

    def start_monitoring(self):
        try:
            if not os.path.exists(BACKUP_FOLDER):
                main_logger.critical(f"[CRITICAL] Der Überwachungsordner existiert nicht: {BACKUP_FOLDER}")
                QtWidgets.QMessageBox.critical(None, 'Fehler', f'Der Überwachungsordner existiert nicht:\n{BACKUP_FOLDER}')
                return

            main_logger.info(f"[MONITOR] Starten der Überwachung des Ordners: {BACKUP_FOLDER}")
            event_handler = BackupEventHandler(self.signals)
            observer = Observer()
            observer.schedule(event_handler, BACKUP_FOLDER, recursive=True)
            observer.start()
            self.clean_old_logs()  # Alte Logs bereinigen beim Start
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                observer.stop()
            observer.join()
        except Exception as e:
            error_message = f"Fehler beim Starten der Überwachung: {e}"
            main_logger.error(f"[ERROR] {error_message}")
            self.signals.error_occurred.emit(error_message)

    def show_gui(self, img_path):
        main_logger.debug(f"[MAIN] Öffnen der GUI für: {img_path}")
        # Erstellen Sie die GUI im Hauptthread
        QtCore.QMetaObject.invokeMethod(self, "create_gui", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, img_path))

    @QtCore.pyqtSlot(str)
    def create_gui(self, img_path):
        gui = ShrinkGUI(img_path)
        gui.show()
        self.guis.append(gui)  # Referenz behalten
        main_logger.debug("[MAIN] ShrinkGUI erstellt und angezeigt.")

    def show_error_dialog(self, error_message):
        self.error_dialog = QtWidgets.QMessageBox()
        self.error_dialog.setIcon(QtWidgets.QMessageBox.Warning)
        self.error_dialog.setWindowTitle("Fehler")
        self.error_dialog.setText("Ein Fehler ist aufgetreten:")
        self.error_dialog.setInformativeText(error_message)
        self.error_dialog.setStandardButtons(QtWidgets.QMessageBox.Ok)
        self.error_dialog.show()  # Fenster bleibt offen
        main_logger.error(f"[ERROR] {error_message}")

    def clean_old_logs(self):
        # Lösche Hauptprozess-Logs älter als 2 Monate (60 Tage)
        cutoff_time = datetime.datetime.now() - datetime.timedelta(days=60)
        if os.path.exists(main_log_filename):
            try:
                modification_time = datetime.datetime.fromtimestamp(os.path.getmtime(main_log_filename))
                if modification_time < cutoff_time:
                    os.remove(main_log_filename)
                    main_logger.info(f"[CLEAN] Alte Haupt-Log-Datei gelöscht: {main_log_filename}")
            except Exception as e:
                main_logger.error(f"[ERROR] Konnte alte Haupt-Log-Datei nicht löschen: {e}")

        # Lösche Shrink-Logs älter als 2 Monate
        for root, dirs, files in os.walk(BACKUP_FOLDER):
            for file in files:
                if file == "shrink.log":
                    shrink_log_path = os.path.join(root, file)
                    try:
                        modification_time = datetime.datetime.fromtimestamp(os.path.getmtime(shrink_log_path))
                        if modification_time < cutoff_time:
                            os.remove(shrink_log_path)
                            main_logger.info(f"[CLEAN] Alte Shrink-Log-Datei gelöscht: {shrink_log_path}")
                    except Exception as e:
                        main_logger.error(f"[ERROR] Konnte alte Shrink-Log-Datei nicht löschen: {e}")

# ======================
# Hauptfunktion
# ======================

def main():
    app = MainApp(sys.argv)
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
