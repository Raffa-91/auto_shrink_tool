# config.py

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
