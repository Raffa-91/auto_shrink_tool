# settings_dialog.py

import os
import json
from PyQt5 import QtWidgets
from log_handler import main_logger

SETTINGS_FILE = "settings.json"
saved_settings = {
    'options': [],
    'logging_enabled': False,
    'advanced_logging': False,
    'delete_backups': False,
    'delete_hours': 168  # Standardmäßig 168 Stunden (7 Tage)
}

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
