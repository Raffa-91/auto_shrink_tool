# shrink_gui.py

import os
import subprocess
import threading
import logging
from PyQt5 import QtCore, QtWidgets
from log_handler import main_logger
from output_dialog import OutputDialog
from shrink_utils import update_space_label, delete_old_backups
from shrink_settings import load_settings, save_settings, DEFAULT_OPTIONS

PISHRINK_SCRIPT = "/home/raphi/pythonScripts/auto_dd_shrinker/pishrink.sh"

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
        layout.addWidget(QtWidgets.QLabel('Auszuführender Befehl:'))
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
        self.logging_switch = QtWidgets.QCheckBox("Log-Datei erstellen")
        options_layout.addWidget(self.logging_switch)
        self.advanced_logging_checkbox = QtWidgets.QCheckBox("Erweitertes Log")
        options_layout.addWidget(self.advanced_logging_checkbox)
        self.delete_backups_switch = QtWidgets.QCheckBox("Ältere Backups löschen")
        options_layout.addWidget(self.delete_backups_switch)
        self.hours_input = QtWidgets.QSpinBox()
        self.hours_input.setRange(1, 5000)  # Erhöhtes Maximum
        self.hours_input.setValue(load_settings().get('delete_hours', 168))
        options_layout.addWidget(self.hours_input)
        options_layout.addWidget(QtWidgets.QLabel("Stunden"))
        layout.addLayout(options_layout)

        # Timer und Speicherplatz Anzeige
        timer_layout = QtWidgets.QHBoxLayout()
        self.timer_label = QtWidgets.QLabel(f"Automatischer Start in {self.time_left} Sekunden")
        timer_layout.addWidget(self.timer_label)
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
        self.load_settings()
        self.timer.timeout.connect(self.update_timer)
        self.timer.start(1000)  # Jede Sekunde
        update_space_label(self.img_path, self.space_label)
        self.update_command()

    def update_command(self):
        options = ' '.join([opt for opt, cb in self.option_checks.items() if cb.isChecked()])
        command = f'sudo bash "{PISHRINK_SCRIPT}" {options} "{self.img_path}"'
        self.command_edit.setText(command)

    def save_settings(self):
        settings = {
            'options': [opt for opt, cb in self.option_checks.items() if cb.isChecked()],
            'logging_enabled': self.logging_switch.isChecked(),
            'advanced_logging': self.advanced_logging_checkbox.isChecked(),
            'delete_backups': self.delete_backups_switch.isChecked(),
            'delete_hours': self.hours_input.value()
        }
        save_settings(settings)
        QtWidgets.QMessageBox.information(self, 'Einstellungen', 'Einstellungen gespeichert.')

    def load_settings(self):
        settings = load_settings()
        for opt, cb in self.option_checks.items():
            cb.setChecked(opt in settings.get('options', []))
        self.logging_switch.setChecked(settings.get('logging_enabled', False))
        self.advanced_logging_checkbox.setChecked(settings.get('advanced_logging', False))
        self.delete_backups_switch.setChecked(settings.get('delete_backups', False))
        self.hours_input.setValue(settings.get('delete_hours', 168))
        self.update_command()

    def update_timer(self):
        self.time_left -= 1
        self.timer_label.setText(f"Automatischer Start in {self.time_left} Sekunden")
        if self.time_left <= 0:
            self.run_command()

    def run_command(self):
        command = self.command_edit.text()
        main_logger.info(f"[SHRINK] Ausführen des Befehls: {command}")
        if self.logging_switch.isChecked():
            shrink_log_path = os.path.join(os.path.dirname(self.img_path), "shrink.log")
            shrink_logger = logging.getLogger(f'Shrink_{os.path.basename(self.img_path)}')
            shrink_logger.setLevel(logging.DEBUG if self.advanced_logging_checkbox.isChecked() else logging.INFO)
            shrink_file_handler = logging.FileHandler(shrink_log_path)
            shrink_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            if shrink_logger.hasHandlers():
                shrink_logger.handlers.clear()
            shrink_logger.addHandler(shrink_file_handler)
        else:
            shrink_logger = None

        shrink_log_path = os.path.join(os.path.dirname(self.img_path), "shrink.log")
        self.output_dialog = OutputDialog(shrink_log_path)
        self.output_dialog.show()
        threading.Thread(target=self.run_process, args=(command, shrink_logger, shrink_log_path), daemon=True).start()
        self.timer.stop()
        self.close()

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
        self.error_dialog.show()
        main_logger.error(f"[ERROR] {error_message}")

    def post_process(self):
        if self.delete_backups_switch.isChecked():
            hours = self.hours_input.value()
            main_logger.info(f"[DELETE] Lösche Backups älter als {hours} Stunden")
            try:
                delete_old_backups(self.img_path, hours)
            except Exception as e:
                self.show_error_dialog(str(e))
        else:
            main_logger.info("[DELETE] Löschfunktion nicht aktiviert.")
