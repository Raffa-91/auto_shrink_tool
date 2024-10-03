# backup_monitor.py

import os
import re
import time
import threading
import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PyQt5 import QtCore
from log_handler import main_logger

# Konfigurationsvariablen
BACKUP_FOLDER_PATTERN = r"raspihaupt-dd-backup-(\d{8})-(\d{6})"

# Worker Signals
class WorkerSignals(QtCore.QObject):
    new_image = QtCore.pyqtSignal(str)
    error_occurred = QtCore.pyqtSignal(str)

# Backup Event Handler
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
