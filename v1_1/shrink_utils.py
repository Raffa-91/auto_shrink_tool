# shrink_utils.py

import os
import datetime
import shutil
import re
from log_handler import main_logger

def update_space_label(img_path, label):
    try:
        statvfs = os.statvfs(img_path)
        free = statvfs.f_bavail * statvfs.f_frsize
        free_gb = free / (2**30)  # In GB umwandeln
        label.setText(f"Freier Speicherplatz: {free_gb:.2f} GB")
        main_logger.debug(f"[SPACE] Freier Speicherplatz: {free_gb:.2f} GB")
    except Exception as e:
        label.setText("Speicherplatz: N/A")
        main_logger.error(f"[ERROR] Konnte Speicherplatz nicht abrufen: {e}")

def delete_old_backups(img_path, hours):
    backup_dir = os.path.dirname(os.path.dirname(img_path))
    main_logger.debug(f"[DELETE] Backup-Verzeichnis: {backup_dir}")
    cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=hours)
    backups_found = False  # Flag, um zu überprüfen, ob Backups gefunden wurden
    for item in os.listdir(backup_dir):
        item_path = os.path.join(backup_dir, item)
        if os.path.isdir(item_path):
            folder_name = os.path.basename(item_path)
            main_logger.debug(f"[DELETE] Überprüfe Ordner: {folder_name}")
            if item_path == os.path.dirname(img_path):
                main_logger.debug(f"[DELETE] Überspringe aktuelles Backup: {item_path}")
                continue  # Überspringen des aktuellen Backups
            match = re.match(r'(\d{8})_(\d{6})', folder_name)
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
                            raise Exception(error_message)
                except ValueError as ve:
                    main_logger.error(f"[ERROR] Ungültiges Datum/Uhrzeit im Ordnernamen {folder_name}: {ve}")
            else:
                main_logger.debug(f"[DELETE] Ordner {folder_name} entspricht nicht dem Muster und wird übersprungen.")
    if not backups_found:
        main_logger.info("[DELETE] Keine alten Backups zum Löschen gefunden.")
    else:
        main_logger.info("[DELETE] Löschvorgang abgeschlossen.")
