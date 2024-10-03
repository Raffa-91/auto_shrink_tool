#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import time
import threading
import subprocess
import shutil
import logging
import json
from PyQt5 import QtCore, QtWidgets, QtGui
from watchdog.events import FileSystemEventHandler

# Konfigurationsvariablen
BACKUP_FOLDER = "/media/raphi/hdd/backups/raspiHauptDD/raspihaupt"
PISHRINK_SCRIPT = "/home/raphi/pythonScripts/auto_dd_shrinker/pishrink.sh"
ICON_PATH = "/home/raphi/pythonScripts/auto_dd_shrinker/icon.png"
SETTINGS_FILE = "settings.json"

# Muster für Backup-Ordner
BACKUP_FOLDER_PATTERN = r"raspihaupt-dd-backup-\d{8}-\d{6}"

# Aktuelle Optionen von PiShrink
DEFAULT_OPTIONS = {
    '-a': 'Automatisch alle Fragen mit Ja beantworten',
    '-d': 'Debug-Nachrichten ausgeben',
    '-r': 'Log-Dateien entfernen',
    '-f': 'Überprüfung des freien Speicherplatzes überspringen',
    '-s': 'Autoexpand der Partition überspringen',
    '-z': 'Image nach dem Shrinken komprimieren'
}

# Gespeicherte Einstellungen
saved_settings = {
    'options': [],
    'logging_enabled': False,
    'advanced_logging': False,
    'delete_backups': False,
    'delete_hours': 168  # Standardmäßig 168 Stunden (7 Tage)
}

# Logging-Konfiguration
logger = logging.getLogger('AutoDDShrinker')
logger.setLevel(logging.INFO)
log_handler = None

class WorkerSignals(QtCore.QObject):
    new_image = QtCore.pyqtSignal(str)

class BackupEventHandler(FileSystemEventHandler):
    def __init__(self, signals):
        super().__init__()
        self.signals = signals

    def on_created(self, event):
        print(f"[DEBUG] on_created: {event.src_path} (is_directory={event.is_directory})")
        if event.is_directory:
            folder_name = os.path.basename(event.src_path)
            print(f"[DEBUG] Neuer Ordner erstellt: {folder_name}")
            if re.match(BACKUP_FOLDER_PATTERN, folder_name):
                print(f"[DEBUG] Ordnername entspricht dem Muster.")
                threading.Thread(target=self.check_for_img_files, args=(event.src_path,), daemon=True).start()
            else:
                print(f"[DEBUG] Ordnername entspricht nicht dem Muster.")

    def check_for_img_files(self, folder_path):
        print(f"[DEBUG] Überprüfe Ordner auf .img-Dateien: {folder_path}")
        # Warten, bis Dateien in den Ordner kopiert wurden
        time.sleep(5)
        img_files = [f for f in os.listdir(folder_path) if f.endswith('.img')]
        if img_files:
            print(f"[DEBUG] Gefundene .img-Dateien: {img_files}")
            for img_file in img_files:
                img_path = os.path.join(folder_path, img_file)
                threading.Thread(target=self.process_img, args=(img_path,), daemon=True).start()
        else:
            print(f"[DEBUG] Keine .img-Dateien in {folder_path} gefunden.")

    def process_img(self, img_path):
        print(f"[DEBUG] Verarbeitung der Datei: {img_path}")
        time.sleep(5)
        print(f"[DEBUG] Warten abgeschlossen, überprüfe Dateiänderungszeit für {img_path}")
        if time.time() - os.path.getmtime(img_path) > 5:
            print(f"[DEBUG] Datei {img_path} wurde seit mindestens 5 Sekunden nicht geändert.")
            # Sende Signal an Hauptthread
            self.signals.new_image.emit(img_path)
        else:
            print(f"[DEBUG] Datei {img_path} wird noch geschrieben.")

class OutputDialog(QtWidgets.QDialog):
    append_text_signal = QtCore.pyqtSignal(str)
    enable_close_button_signal = QtCore.pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ausgabe")
        self.resize(600, 400)
        
        self.layout = QtWidgets.QVBoxLayout()
        self.output_text = QtWidgets.QPlainTextEdit()
        self.output_text.setReadOnly(True)
        self.layout.addWidget(self.output_text)
        
        self.close_button = QtWidgets.QPushButton("Schließen")
        self.close_button.setEnabled(False)
        self.close_button.clicked.connect(self.close)
        self.layout.addWidget(self.close_button)
        
        self.setLayout(self.layout)
        
        # Signale verbinden
        self.append_text_signal.connect(self.output_text.appendPlainText)
        self.enable_close_button_signal.connect(self.enable_close_button_slot)
        
    def append_output(self, text):
        self.append_text_signal.emit(text)
        
    def enable_close_button_slot(self):
        self.close_button.setEnabled(True)
        
    def enable_close_button(self):
        self.enable_close_button_signal.emit()

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
        layout.addWidget(self.command_edit)

        # PiShrink-Optionen (Checkboxen horizontal angeordnet)
        self.option_checks = {}
        options_layout = QtWidgets.QHBoxLayout()
        for opt, desc in DEFAULT_OPTIONS.items():
            checkbox = QtWidgets.QCheckBox(opt)
            checkbox.stateChanged.connect(self.update_command)
            checkbox.setToolTip(desc)  # Tooltip mit Beschreibung
            options_layout.addWidget(checkbox)
            self.option_checks[opt] = checkbox
        layout.addLayout(options_layout)

        # Optionale Einstellungen (Logging und Löschen älterer Backups)
        options_layout = QtWidgets.QHBoxLayout()

        # Logging Optionen
        self.logging_switch = QtWidgets.QCheckBox("Log-Datei erstellen")
        self.logging_switch.setChecked(saved_settings.get('logging_enabled', False))
        options_layout.addWidget(self.logging_switch)

        self.advanced_logging_checkbox = QtWidgets.QCheckBox("Erweitertes Log")
        self.advanced_logging_checkbox.setChecked(saved_settings.get('advanced_logging', False))
        options_layout.addWidget(self.advanced_logging_checkbox)

        options_layout.addStretch()

        # Ältere Backups löschen
        self.delete_backups_switch = QtWidgets.QCheckBox("Ältere Backups löschen")
        self.delete_backups_switch.setChecked(saved_settings.get('delete_backups', False))
        options_layout.addWidget(self.delete_backups_switch)

        self.hours_dropdown = QtWidgets.QComboBox()
        self.hours_dropdown.addItems([str(i) for i in range(1, 501)])  # 1 bis 500 Stunden
        self.hours_dropdown.setCurrentIndex(saved_settings.get('delete_hours', 168) - 1)
        self.hours_dropdown.currentIndexChanged.connect(self.update_days_label)
        options_layout.addWidget(self.hours_dropdown)

        hours_label = QtWidgets.QLabel("Stunden")
        options_layout.addWidget(hours_label)

        layout.addLayout(options_layout)

        # Anzeige der entsprechenden Tage
        self.days_label = QtWidgets.QLabel()
        layout.addWidget(self.days_label)
        self.update_days_label()

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
        self.save_button.setStyleSheet("font-weight: bold; font-size: 14px;")
        buttons_layout.addWidget(self.save_button)

        self.run_button = QtWidgets.QPushButton('Befehl ausführen')
        self.run_button.clicked.connect(self.run_command)
        self.run_button.setStyleSheet("font-weight: bold; font-size: 14px;")
        buttons_layout.addWidget(self.run_button)

        layout.addLayout(buttons_layout)
        self.setLayout(layout)

        # Gespeicherte Einstellungen laden
        self.load_settings()

        # Timer starten
        self.timer.timeout.connect(self.update_timer)
        self.timer.start(1000)  # Alle 1 Sekunde

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
        saved_settings['delete_hours'] = int(self.hours_dropdown.currentText())
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(saved_settings, f)
        print(f"[DEBUG] Einstellungen gespeichert: {saved_settings}")
        QtWidgets.QMessageBox.information(self, 'Einstellungen', 'Einstellungen gespeichert.')

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                global saved_settings
                saved_settings = json.load(f)
        # Optionen laden
        for opt, cb in self.option_checks.items():
            if opt in saved_settings.get('options', []):
                cb.setChecked(True)
            else:
                cb.setChecked(False)
        # Sonstige Einstellungen laden
        self.logging_switch.setChecked(saved_settings.get('logging_enabled', False))
        self.advanced_logging_checkbox.setChecked(saved_settings.get('advanced_logging', False))
        self.delete_backups_switch.setChecked(saved_settings.get('delete_backups', False))
        self.hours_dropdown.setCurrentIndex(saved_settings.get('delete_hours', 168) - 1)
        self.update_days_label()
        self.update_command()

    def update_days_label(self):
        hours = int(self.hours_dropdown.currentText())
        days = hours / 24
        self.days_label.setText(f"Das entspricht {days:.2f} Tagen.")

    def run_command(self):
        command = self.command_edit.text()
        print(f"[DEBUG] Ausführen des Befehls: {command}")
        # Logging einrichten, falls aktiviert
        global log_handler
        if self.logging_switch.isChecked():
            log_filename = "autodds_shrinker.log"
            if self.advanced_logging_checkbox.isChecked():
                logger.setLevel(logging.DEBUG)
            else:
                logger.setLevel(logging.INFO)
            if not logger.handlers:
                log_handler = logging.FileHandler(log_filename)
                formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
                log_handler.setFormatter(formatter)
                logger.addHandler(log_handler)
            else:
                # Aktualisieren des Log-Levels, falls bereits Handler vorhanden sind
                logger.handlers[0].setLevel(logger.level)
        else:
            # Entferne Handler, wenn Logging nicht aktiviert ist
            logger.handlers = []
        # Logge den Befehl
        logger.info(f"Ausführen des Befehls: {command}")
        # Starte den Befehl in einem neuen Thread
        threading.Thread(target=self.execute_and_cleanup, args=(command,), daemon=True).start()
        self.timer.stop()
        # self.close()  # Entfernt, um das Fenster offen zu halten

    def execute_and_cleanup(self, command):
        # Ausführen des Shrink-Skripts als Subprozess
        try:
            # Dialogfenster zur Ausgabe anzeigen
            self.output_dialog = OutputDialog()
            self.output_dialog.show()
            
            def run_process():
                process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
                # Ausgabe zeilenweise lesen
                for line in process.stdout:
                    self.output_dialog.append_output(line)
                # Warten auf Abschluss des Prozesses
                process.wait()
                # Benachrichtigung über Abschluss
                self.output_dialog.append_output("\nBefehl abgeschlossen.")
                self.output_dialog.enable_close_button()
                
                # Löschen alter Backups, falls aktiviert
                if self.delete_backups_switch.isChecked():
                    hours = int(self.hours_dropdown.currentText())
                    logger.info(f"Lösche Backups älter als {hours} Stunden")
                    current_backup_folder = os.path.dirname(self.img_path)
                    self.delete_old_backups(hours, current_backup_folder)
                else:
                    print("[DEBUG] Löschfunktion nicht aktiviert.")
                
                # Schließen des ShrinkGUI-Fensters nach Abschluss (optional)
                # self.close()
            
            threading.Thread(target=run_process, daemon=True).start()
        except Exception as e:
            print(f"[ERROR] Fehler beim Ausführen des Befehls: {e}")
            logger.error(f"Fehler beim Ausführen des Befehls: {e}")

    def delete_old_backups(self, hours, exclude_folder):
        backup_dir = os.path.dirname(os.path.dirname(self.img_path))
        cutoff_time = time.time() - (hours * 3600)  # Stunden in Sekunden
        for item in os.listdir(backup_dir):
            item_path = os.path.join(backup_dir, item)
            if os.path.isdir(item_path):
                folder_name = os.path.basename(item_path)
                if item_path == exclude_folder:
                    print(f"[DEBUG] Überspringe aktuelles Backup: {item_path}")
                    continue
                if re.match(BACKUP_FOLDER_PATTERN, folder_name):
                    folder_time = os.path.getmtime(item_path)
                    if folder_time < cutoff_time:
                        logger.info(f"Lösche altes Backup: {item_path}")
                        print(f"[DEBUG] Lösche altes Backup: {item_path}")
                        try:
                            shutil.rmtree(item_path)
                        except Exception as e:
                            logger.error(f"Konnte {item_path} nicht löschen: {e}")
                            print(f"[ERROR] Konnte {item_path} nicht löschen: {e}")

    def update_timer(self):
        self.time_left -= 1
        self.timer_label.setText(f"Automatischer Start in {self.time_left} Sekunden")
        if self.time_left % 5 == 0:
            self.update_space_label()
        if self.time_left <= 0:
            print("[DEBUG] Timer abgelaufen, Befehl wird automatisch ausgeführt.")
            self.run_command()

    def update_space_label(self):
        # Freien Speicherplatz aktualisieren
        try:
            statvfs = os.statvfs(self.img_path)
            free = statvfs.f_bavail * statvfs.f_frsize
            free_gb = free // (2**30)  # In GB umwandeln
            self.space_label.setText(f"Freier Speicherplatz: {free_gb} GB")
        except Exception as e:
            self.space_label.setText("Speicherplatz: N/A")
            print(f"[ERROR] Konnte Speicherplatz nicht abrufen: {e}")

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
        QtWidgets.QMessageBox.information(None, 'Status', 'Der Shrink-Skript ist aktiv.')

    def show_logs(self):
        # Öffnet die Log-Datei mit dem Standardeditor
        log_filename = "autodds_shrinker.log"
        if os.path.exists(log_filename):
            subprocess.Popen(['xdg-open', log_filename])
        else:
            QtWidgets.QMessageBox.information(None, 'Logs', 'Keine Log-Datei gefunden.')

    def open_settings(self):
        # Beispielhafte Einstellungen (kann erweitert werden)
        QtWidgets.QMessageBox.information(None, 'Einstellungen', 'Einstellungsdialog kann hier implementiert werden.')
