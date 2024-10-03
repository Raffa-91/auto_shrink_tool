# log_viewer.py

import os
from PyQt5 import QtWidgets
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtCore import QUrl
from log_handler import main_logger

class LogViewer(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Log Viewer")
        self.resize(1000, 700)
        self.layout = QtWidgets.QVBoxLayout()

        # Tabbed Interface für Haupt- und Shrink-Logs
        self.tabs = QtWidgets.QTabWidget()
        self.layout.addWidget(self.tabs)

        # Hauptprozess-Log Tab
        self.main_log_tab = QtWidgets.QWidget()
        self.main_log_layout = QtWidgets.QVBoxLayout()
        self.main_log_text = QtWidgets.QPlainTextEdit()
        self.main_log_text.setReadOnly(True)
        self.main_log_layout.addWidget(self.main_log_text)

        # Button zum Aktualisieren des Haupt-Logs
        self.refresh_main_log_button = QtWidgets.QPushButton('Haupt-Log aktualisieren')
        self.refresh_main_log_button.clicked.connect(self.load_main_logs)
        self.main_log_layout.addWidget(self.refresh_main_log_button)

        self.main_log_tab.setLayout(self.main_log_layout)
        self.tabs.addTab(self.main_log_tab, "Haupt-Log")

        # Shrink-Logs Tab
        self.shrink_logs_tab = QtWidgets.QWidget()
        self.shrink_logs_layout = QtWidgets.QVBoxLayout()

        # Liste der Shrink-Logs
        self.shrink_logs_list = QtWidgets.QListWidget()
        self.shrink_logs_layout.addWidget(self.shrink_logs_list)

        # Button zum Aktualisieren der Shrink-Logs
        self.refresh_shrink_logs_button = QtWidgets.QPushButton('Shrink-Logs aktualisieren')
        self.refresh_shrink_logs_button.clicked.connect(self.load_shrink_logs)
        self.shrink_logs_layout.addWidget(self.refresh_shrink_logs_button)

        self.shrink_logs_tab.setLayout(self.shrink_logs_layout)
        self.tabs.addTab(self.shrink_logs_tab, "Shrink-Logs")

        self.setLayout(self.layout)
        self.load_main_logs()
        self.load_shrink_logs()

    def load_main_logs(self):
        if os.path.exists(main_log_filename):
            with open(main_log_filename, 'r') as f:
                log_content = f.read()
            self.main_log_text.setPlainText(log_content)
            main_logger.debug("[LOGVIEWER] Haupt-Log geladen.")
        else:
            self.main_log_text.setPlainText("Keine Haupt-Log-Datei gefunden.")
            main_logger.warning("[LOGVIEWER] Haupt-Log-Datei nicht gefunden.")

    def load_shrink_logs(self):
        self.shrink_logs_list.clear()
        for root, dirs, files in os.walk(BACKUP_FOLDER):
            if "shrink.log" in files:
                shrink_log_path = os.path.join(root, "shrink.log")
                backup_folder = os.path.basename(root)
                list_item = QtWidgets.QListWidgetItem(backup_folder)
                widget = QtWidgets.QWidget()
                layout = QtWidgets.QHBoxLayout()
                layout.setContentsMargins(5, 5, 5, 5)

                label = QtWidgets.QLabel(backup_folder)
                view_button = QtWidgets.QPushButton("Shrink-Log anzeigen")
                # Korrekte Bindung des shrink_log_path zu jedem Button
                view_button.clicked.connect(lambda checked, path=shrink_log_path: self.open_shrink_log(path))

                layout.addWidget(label)
                layout.addStretch()
                layout.addWidget(view_button)
                widget.setLayout(layout)

                list_item.setSizeHint(widget.sizeHint())
                self.shrink_logs_list.addItem(list_item)
                self.shrink_logs_list.setItemWidget(list_item, widget)
        main_logger.debug("[LOGVIEWER] Shrink-Logs geladen.")

    def open_shrink_log(self, shrink_log_path):
        if os.path.exists(shrink_log_path):
            try:
                # Öffne das Shrink-Log mit dem Standard-Texteditor
                QDesktopServices.openUrl(QUrl.fromLocalFile(shrink_log_path))
                main_logger.info(f"[LOGVIEWER] Öffne Shrink-Log: {shrink_log_path}")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Fehler", f"Kann Shrink-Log nicht öffnen: {e}")
                main_logger.error(f"[LOGVIEWER ERROR] Kann Shrink-Log nicht öffnen: {e}")
        else:
            QtWidgets.QMessageBox.information(self, "Info", "Shrink-Log-Datei nicht gefunden.")
            main_logger.warning("[LOGVIEWER] Shrink-Log-Datei nicht gefunden.")
