import os
import sys
import time
import threading
from PyQt5 import QtWidgets, QtCore
from watchdog.observers import Observer
from config import BACKUP_FOLDER, ICON_PATH
from logging_setup import main_logger
from signals import WorkerSignals
from event_handler import BackupEventHandler
from tray_icon import SystemTrayIcon
from gui import ShrinkGUI

class MainApp(QtWidgets.QApplication):
    def __init__(self, sys_argv):
        super().__init__(sys_argv)
        self.setQuitOnLastWindowClosed(False)
        self.tray_icon = SystemTrayIcon(ICON_PATH)
        self.tray_icon.show()
        main_logger.debug("[MAIN] Tray-Icon gestartet.")
        self.signals = WorkerSignals()
        self.signals.new_image.connect(self.show_gui)
        self.signals.error_occurred.connect(self.show_error_dialog)
        self.monitoring_thread = threading.Thread(target=self.start_monitoring, daemon=True)
        self.monitoring_thread.start()
        main_logger.debug("[MAIN] Überwachungsthread gestartet.")
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
            self.clean_old_logs()
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
        QtCore.QMetaObject.invokeMethod(self, "create_gui", QtCore.Qt.QueuedConnection, QtCore.Q_ARG(str, img_path))

    @QtCore.pyqtSlot(str)
    def create_gui(self, img_path):
        gui = ShrinkGUI(img_path)
        gui.show()
        self.guis.append(gui)
        main_logger.debug("[MAIN] ShrinkGUI erstellt und angezeigt.")

    def show_error_dialog(self, error_message):
        error_dialog = QtWidgets.QMessageBox()
        error_dialog.setIcon(QtWidgets.QMessageBox.Warning)
        error_dialog.setWindowTitle("Fehler")
        error_dialog.setText("Ein Fehler ist aufgetreten:")
        error_dialog.setInformativeText(error_message)
        error_dialog.setStandardButtons(QtWidgets.QMessageBox.Ok)
        error_dialog.show()
        main_logger.error(f"[ERROR] {error_message}")

    def clean_old_logs(self):
        cutoff_time = datetime.datetime.now() - datetime.timedelta(days=60)
        if os.path.exists(main_log_filename):
            try:
                modification_time = datetime.datetime.fromtimestamp(os.path.getmtime(main_log_filename))
                if modification_time < cutoff_time:
                    os.remove(main_log_filename)
                    main_logger.info(f"[CLEAN] Alte Haupt-Log-Datei gelöscht: {main_log_filename}")
            except Exception as e:
                main_logger.error(f"[ERROR] Konnte alte Haupt-Log-Datei nicht löschen: {e}")

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

def main():
    app = MainApp(sys.argv)
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
