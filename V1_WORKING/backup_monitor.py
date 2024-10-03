# V0.1a/backup_monitor.py
import os
import time
import threading
import re
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from PyQt5.QtCore import pyqtSignal, QObject
from log_handler import logger  # Zentralen Logger importieren

class WorkerSignals(QObject):
    new_image = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

class BackupEventHandler(FileSystemEventHandler):
    def __init__(self, signals, backup_folder, backup_pattern):
        super().__init__()
        self.signals = signals
        self.backup_folder = backup_folder
        self.backup_pattern = backup_pattern
        self.monitored_folders = set()

    def on_created(self, event):
        self.process_event(event)

    def on_modified(self, event):
        self.process_event(event)

    def process_event(self, event):
        logger.debug(f"[EVENT] Event erkannt: {event.src_path}")
        try:
            if event.is_directory:
                folder_name = os.path.basename(event.src_path)
                if re.match(self.backup_pattern, folder_name):
                    if event.src_path not in self.monitored_folders:
                        self.monitored_folders.add(event.src_path)
                        threading.Thread(target=self.monitor_new_folder, args=(event.src_path,), daemon=True).start()
            else:
                if os.path.basename(event.src_path) == "raspiBackup.log":
                    folder_path = os.path.dirname(event.src_path)
                    if folder_path not in self.monitored_folders:
                        folder_name = os.path.basename(folder_path)
                        if re.match(self.backup_pattern, folder_name):
                            self.monitored_folders.add(folder_path)
                            threading.Thread(target=self.monitor_new_folder, args=(folder_path,), daemon=True).start()
        except Exception as e:
            error_message = f"Fehler bei der Verarbeitung des Ereignisses {event.src_path}: {e}"
            logger.error(f"[ERROR] {error_message}")
            self.signals.error_occurred.emit(error_message)

    def monitor_new_folder(self, folder_path):
        log_file_path = os.path.join(folder_path, "raspiBackup.log")
        while True:
            if os.path.exists(log_file_path):
                logger.info(f"[FOUND] raspiBackup.log gefunden: {log_file_path}")
                time.sleep(10)  # Warten, bis das Log-File vollständig geschrieben ist
                img_files = [f for f in os.listdir(folder_path) if f.endswith('.img')]
                if img_files:
                    for img_file in img_files:
                        img_path = os.path.join(folder_path, img_file)
                        self.signals.new_image.emit(img_path)
                else:
                    logger.warning(f"[WARNING] Keine .img-Datei im Ordner gefunden: {folder_path}")
                break
            else:
                time.sleep(5)
