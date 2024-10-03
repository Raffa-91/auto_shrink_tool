import sys
import os
import json
import threading
import datetime
import time
from PyQt5 import QtWidgets, QtGui
from PyQt5.QtWidgets import QFileDialog
from log_handler import logger  # Zentralen Logger importieren
from backup_monitor import BackupEventHandler, WorkerSignals
from gui import ShrinkGUI, LogViewer, SettingsDialog
from watchdog.observers import Observer

def wait_for_mount(mount_point, timeout=60, interval=2):
    """
    Warte, bis der angegebene Mount-Punkt gemountet ist.

    :param mount_point: Pfad zum Mount-Punkt (z.B. /media/raphi/hdd/)
    :param timeout: Maximale Wartezeit in Sekunden
    :param interval: Überprüfungsintervall in Sekunden
    :return: True, wenn gemountet; False sonst
    """
    start_time = datetime.datetime.now()
    while not os.path.ismount(mount_point):
        elapsed = (datetime.datetime.now() - start_time).seconds
        if elapsed >= timeout:
            logger.error(f"Timeout: Mount-Punkt {mount_point} nicht gefunden nach {timeout} Sekunden.")
            return False
        logger.info(f"Mount-Punkt {mount_point} nicht gefunden. Warte weitere {interval} Sekunden...")
        time.sleep(interval)
    logger.info(f"Mount-Punkt {mount_point} ist gemountet.")
    return True

def main():
    """
    Hauptfunktion der Anwendung.
    """
    # Pfad zum Mount-Punkt
    mount_point = "/media/raphi/hdd/"
    # Maximale Wartezeit in Sekunden
    mount_timeout = 60
    # Warteintervall in Sekunden
    mount_interval = 2

    # Warten, bis der Mount-Punkt verfügbar ist
    if not wait_for_mount(mount_point, timeout=mount_timeout, interval=mount_interval):
        # Mount-Punkt nicht verfügbar, zeigen eine Fehlermeldung und beenden
        print(f"Mount-Punkt {mount_point} nicht verfügbar nach {mount_timeout} Sekunden.")
        sys.exit(1)

    # Starten der PyQt-Anwendung
    app = QtWidgets.QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Verhindern, dass die App beendet wird, wenn Fenster geschlossen werden

    logger.debug("PyQt-Anwendung gestartet.")

    # Pfade definieren
    script_dir = os.path.dirname(os.path.realpath(__file__))
    settings_file = os.path.join(script_dir, 'settings.json')
    icon_path = os.path.join(script_dir, 'icon.png')
    logger.debug(f"Script-Verzeichnis: {script_dir}")
    logger.debug(f"Einstellungsdatei: {settings_file}")
    logger.debug(f"Icon-Pfad: {icon_path}")

    # Backup-Verzeichnisse aus den Einstellungen laden
    backup_folders = load_backup_folders(settings_file)
    if not backup_folders:
        logger.warning("Keine Backup-Verzeichnisse gefunden.")
        # Backup-Verzeichnisse existieren nicht, informieren und erlauben Auswahl neuer Verzeichnisse
        msg_box = QtWidgets.QMessageBox()
        msg_box.setIcon(QtWidgets.QMessageBox.Warning)
        msg_box.setWindowTitle("Backup-Verzeichnisse nicht gefunden")
        msg_box.setText("Es wurden keine Backup-Verzeichnisse gefunden.")
        msg_box.setInformativeText("Bitte wählen Sie neue Backup-Verzeichnisse aus.")
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
        ret = msg_box.exec_()

        if ret == QtWidgets.QMessageBox.Ok:
            # Benutzer wählt neue Backup-Verzeichnisse
            new_dirs = QFileDialog.getExistingDirectory(None, "Neue Backup-Verzeichnisse wählen", "/media/raphi/hdd/backups/")
            if new_dirs:
                backup_folders = [new_dirs]
                save_backup_folders(settings_file, backup_folders)
                logger.info(f"[CONFIG] Neue Backup-Verzeichnisse festgelegt: {backup_folders}")
            else:
                # Keine Verzeichnisse ausgewählt, beenden
                msg_box_2 = QtWidgets.QMessageBox()
                msg_box_2.setIcon(QtWidgets.QMessageBox.Critical)
                msg_box_2.setWindowTitle("Fehler")
                msg_box_2.setText("Keine gültigen Backup-Verzeichnisse ausgewählt.")
                msg_box_2.setInformativeText("Die Anwendung kann nicht gestartet werden ohne gültige Backup-Verzeichnisse.")
                msg_box_2.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg_box_2.exec_()
                logger.critical("[CRITICAL] Keine gültigen Backup-Verzeichnisse ausgewählt. Anwendung wird beendet.")
                sys.exit(1)
        else:
            # Benutzer hat abgebrochen
            msg_box_3 = QtWidgets.QMessageBox()
            msg_box_3.setIcon(QtWidgets.QMessageBox.Information)
            msg_box_3.setWindowTitle("Information")
            msg_box_3.setText("Die Anwendung wird ohne Überwachung der Backup-Verzeichnisse ausgeführt.")
            msg_box_3.setInformativeText("Sie können die Backup-Verzeichnisse später in den Einstellungen ändern.")
            msg_box_3.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg_box_3.exec_()
            logger.warning("[WARNING] Backup-Verzeichnisse nicht verfügbar. Anwendung läuft ohne Überwachung.")

    # Liste zur Aufbewahrung der Referenzen auf offene Dialoge
    dialogs = []

    # Signale
    signals = WorkerSignals()
    signals.new_image.connect(lambda img_path: open_shrink_gui(app, img_path, settings_file, dialogs))
    signals.error_occurred.connect(lambda error: show_error(app, error, dialogs))

    # Tray-Icon erstellen und anzeigen
    tray_icon = create_tray_icon(app, settings_file, backup_folders, icon_path, dialogs)

    # Backup Event Handler und Observer
    backup_pattern = r"raspihaupt-dd-backup-(\d{8})-(\d{6})"
    event_handler = BackupEventHandler(signals, backup_folders, backup_pattern)
    observer = Observer()
    for folder in backup_folders:
        observer.schedule(event_handler, folder, recursive=True)
    observer.start()
    logger.info(f"[MAIN] Starten der Überwachung der Ordner: {backup_folders}")

    # Starten des Log-Reinigungsprozesses
    threading.Thread(target=clean_old_logs, args=(backup_folders,), daemon=True).start()
    logger.debug("Log-Reinigungsprozess gestartet.")

    # System-Tray-Icon anzeigen
    tray_icon.show()
    logger.debug("System-Tray-Icon angezeigt.")

    # Starten des Event-Loops
    logger.debug("Anwendung in den Event-Loop gestartet.")
    sys.exit(app.exec_())

def create_tray_icon(app, settings_file, backup_folders, icon_path, dialogs):
    """
    Erstellen und konfigurieren des System-Tray-Icons.

    :param app: QApplication-Instanz
    :param settings_file: Pfad zur Einstellungsdatei
    :param backup_folders: Liste der Backup-Verzeichnisse
    :param icon_path: Pfad zum Icon
    :param dialogs: Liste zur Aufbewahrung der Referenzen auf Dialoge
    :return: QSystemTrayIcon-Instanz
    """
    try:
        if not os.path.exists(icon_path):
            logger.error(f"Icon-Datei nicht gefunden: {icon_path}")
            raise FileNotFoundError(f"Icon-Datei nicht gefunden: {icon_path}")
        
        icon = QtGui.QIcon(icon_path)
        if icon.isNull():
            logger.error(f"Fehler beim Laden des Icons: {icon_path}")
            raise ValueError(f"Fehler beim Laden des Icons: {icon_path}")
        
        tray_icon = QtWidgets.QSystemTrayIcon(icon, parent=None)
        tray_menu = QtWidgets.QMenu()

        # Menüeinträge
        show_logs_action = tray_menu.addAction("Logs anzeigen")
        show_logs_action.triggered.connect(lambda: open_log_viewer(app, backup_folders, dialogs))

        open_settings_action = tray_menu.addAction("Einstellungen öffnen")
        open_settings_action.triggered.connect(lambda: open_settings(app, settings_file, dialogs))

        quit_action = tray_menu.addAction("Beenden")
        quit_action.triggered.connect(app.quit)

        tray_icon.setContextMenu(tray_menu)
        tray_icon.setToolTip("Auto DD Shrinker")
        tray_icon.show()
        logger.info("System-Tray-Icon erfolgreich erstellt und angezeigt.")
        return tray_icon
    except Exception as e:
        logger.exception(f"Fehler beim Erstellen des Tray-Icons: {e}")
        QtWidgets.QMessageBox.critical(None, "Fehler", f"Tray-Icon konnte nicht erstellt werden:\n{e}")
        sys.exit(1)

def open_shrink_gui(app, img_path, settings_file, dialogs):
    """
    Öffnet das ShrinkGUI-Fenster.

    :param app: QApplication-Instanz
    :param img_path: Pfad zum Image
    :param settings_file: Pfad zur Einstellungsdatei
    :param dialogs: Liste zur Aufbewahrung der Referenzen auf Dialoge
    """
    gui = ShrinkGUI(img_path, settings_file)
    gui.show()
    dialogs.append(gui)  # Halten Sie eine Referenz
    logger.debug("[MAIN] ShrinkGUI erstellt und angezeigt.")

def open_log_viewer(app, backup_folders, dialogs):
    """
    Öffnet das LogViewer-Fenster.

    :param app: QApplication-Instanz
    :param backup_folders: Liste der Backup-Verzeichnisse
    :param dialogs: Liste zur Aufbewahrung der Referenzen auf Dialoge
    """
    main_log_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'autodds_monitor.log')
    # Standardwert für Tage zum Löschen von Logs, z.B. 7 Tage
    delete_days = 7
    log_viewer = LogViewer(main_log_filename, backup_folders, r"raspihaupt-dd-backup-(\d{8})-(\d{6})", delete_days=delete_days)
    log_viewer.show()
    dialogs.append(log_viewer)  # Halten Sie eine Referenz
    logger.debug("[TRAY] Log Viewer geöffnet.")

def open_settings(app, settings_file, dialogs):
    """
    Öffnet das SettingsDialog-Fenster.

    :param app: QApplication-Instanz
    :param settings_file: Pfad zur Einstellungsdatei
    :param dialogs: Liste zur Aufbewahrung der Referenzen auf Dialoge
    """
    settings_dialog = SettingsDialog(settings_file)
    settings_dialog.show()
    dialogs.append(settings_dialog)  # Halten Sie eine Referenz
    logger.debug("[TRAY] SettingsDialog geöffnet.")

def show_error(app, error_message, dialogs):
    """
    Zeigt eine Fehlermeldung an.

    :param app: QApplication-Instanz
    :param error_message: Fehlermeldungstext
    :param dialogs: Liste zur Aufbewahrung der Referenzen auf Dialoge
    """
    msg_box = QtWidgets.QMessageBox()
    msg_box.setIcon(QtWidgets.QMessageBox.Warning)
    msg_box.setWindowTitle("Fehler")
    msg_box.setText("Ein Fehler ist aufgetreten:")
    msg_box.setInformativeText(error_message)
    msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
    msg_box.exec_()
    logger.error(f"[ERROR] {error_message}")

def clean_old_logs(backup_folders):
    """
    Löscht alte Log-Dateien, die älter als 60 Tage sind.

    :param backup_folders: Liste der Backup-Verzeichnisse
    """
    main_log_filename = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'autodds_monitor.log')
    cutoff_time = datetime.datetime.now() - datetime.timedelta(days=60)
    # Lösche Hauptprozess-Logs älter als 2 Monate (60 Tage)
    if os.path.exists(main_log_filename):
        try:
            modification_time = datetime.datetime.fromtimestamp(os.path.getmtime(main_log_filename))
            if modification_time < cutoff_time:
                os.remove(main_log_filename)
                logger.info(f"[CLEAN] Alte Haupt-Log-Datei gelöscht: {main_log_filename}")
        except Exception as e:
            logger.error(f"[ERROR] Konnte alte Haupt-Log-Datei nicht löschen: {e}")

    # Lösche Shrink-Logs älter als 2 Monate
    for folder in backup_folders:
        for root, dirs, files in os.walk(folder):
            for file in files:
                if file == "shrink.log":
                    shrink_log_path = os.path.join(root, file)
                    try:
                        modification_time = datetime.datetime.fromtimestamp(os.path.getmtime(shrink_log_path))
                        if modification_time < cutoff_time:
                            os.remove(shrink_log_path)
                            logger.info(f"[CLEAN] Alte Shrink-Log-Datei gelöscht: {shrink_log_path}")
                    except Exception as e:
                        logger.error(f"[ERROR] Konnte alte Shrink-Log-Datei nicht löschen: {e}")

def load_backup_folders(settings_file):
    """
    Lädt die Backup-Verzeichnisse aus der Einstellungsdatei.

    :param settings_file: Pfad zur Einstellungsdatei
    :return: Liste der Backup-Verzeichnisse
    """
    if os.path.exists(settings_file):
        with open(settings_file, 'r') as f:
            settings = json.load(f)
            return settings.get('backup_folders', [])
    return []

def save_backup_folders(settings_file, backup_folders):
    """
    Speichert die Backup-Verzeichnisse in der Einstellungsdatei.

    :param settings_file: Pfad zur Einstellungsdatei
    :param backup_folders: Liste der Backup-Verzeichnisse
    """
    settings = {}
    if os.path.exists(settings_file):
        with open(settings_file, 'r') as f:
            settings = json.load(f)
    settings['backup_folders'] = backup_folders
    with open(settings_file, 'w') as f:
        json.dump(settings, f, indent=4)

if __name__ == '__main__':
    main()
