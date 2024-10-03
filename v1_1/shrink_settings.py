# shrink_settings.py

import os
import json
from log_handler import main_logger

SETTINGS_FILE = "settings.json"
DEFAULT_OPTIONS = {
    '-a': 'Automatisch alle Fragen mit Ja beantworten',
    '-d': 'Debug-Nachrichten ausgeben',
    '-r': 'Log-Dateien entfernen',
    '-f': 'Überprüfung des freien Speicherplatzes überspringen',
    '-s': 'Autoexpand der Partition überspringen',
    '-z': 'Image nach dem Shrinken komprimieren'
}
saved_settings = {
    'options': [],
    'logging_enabled': False,
    'advanced_logging': False,
    'delete_backups': False,
    'delete_hours': 168  # Standardmäßig 168 Stunden (7 Tage)
}

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            global saved_settings
            saved_settings = json.load(f)
    return saved_settings

def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f)
    main_logger.info("[SETTINGS] Einstellungen gespeichert.")
