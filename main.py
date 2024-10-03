#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import threading
import time
from PyQt5 import QtWidgets
from watchdog.observers import Observer

# Import der benötigten Komponenten aus auto_dd_shrinker
from auto_dd_shrinker import (
    BACKUP_FOLDER, ICON_PATH,
    WorkerSignals, BackupEventHandler,
    ShrinkGUI, SystemTrayIcon
)

class MainApp(QtWidgets.QApplication):
    def __init__(self, sys_argv):
        super().__init__(sys_argv)

        # Tray-Icon
        self.tray_icon = SystemTrayIcon(ICON_PATH)
        self.tray_icon.show()
        print("[DEBUG] Tray-Icon gestartet.")

        # Signale
        self.signals = WorkerSignals()
        self.signals.new_image.connect(self.show_gui)

        # Überwachung in separatem Thread starten
        self.monitoring_thread = threading.Thread(target=self.start_monitoring, daemon=True)
        self.monitoring_thread.start()
        print("[DEBUG] Überwachungsthread gestartet.")

    def start_monitoring(self):
        print(f"[DEBUG] Starten der Überwachung des Ordners: {BACKUP_FOLDER}")
        event_handler = BackupEventHandler(self.signals)
        observer = Observer()
        observer.schedule(event_handler, BACKUP_FOLDER, recursive=True)
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

    def show_gui(self, img_path):
        print(f"[DEBUG] Öffnen der GUI für: {img_path}")
        self.gui = ShrinkGUI(img_path)
        self.gui.show()

def main():
    app = MainApp(sys.argv)
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
