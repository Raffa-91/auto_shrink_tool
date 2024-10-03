# output_dialog.py

import os
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from log_handler import main_logger

class OutputDialog(QtWidgets.QDialog):
    append_text_signal = QtCore.pyqtSignal(str)

    def __init__(self, shrink_log_path):
        super().__init__()
        self.setWindowTitle("Ausgabe des Shrink-Skripts")
        self.resize(800, 600)
        self.layout = QtWidgets.QVBoxLayout()

        # Textbereich für die Ausgabe
        self.output_text = QtWidgets.QPlainTextEdit()
        self.output_text.setReadOnly(True)
        self.layout.addWidget(self.output_text)

        # Button zum Schließen mit Countdown
        self.close_button = QtWidgets.QPushButton()
        self.close_button.clicked.connect(self.close)
        self.layout.addWidget(self.close_button)

        # Button zum Öffnen des Shrink-Logs
        self.view_shrink_log_button = QtWidgets.QPushButton("Shrink-Log anzeigen")
        self.view_shrink_log_button.clicked.connect(lambda: self.open_shrink_log(shrink_log_path))
        self.layout.addWidget(self.view_shrink_log_button)

        self.setLayout(self.layout)

        # Signal-Verbindungen
        self.append_text_signal.connect(self.output_text.appendPlainText)

        # Timer zum automatischen Schließen nach 5 Minuten (300 Sekunden)
        self.remaining_time = 300  # Sekunden
        self.update_close_button()
        self.auto_close_timer = QtCore.QTimer(self)
        self.auto_close_timer.setInterval(1000)  # 1 Sekunde
        self.auto_close_timer.timeout.connect(self.update_timer)
        self.auto_close_timer.start()

    def append_output(self, text):
        self.append_text_signal.emit(text)

    def update_close_button(self):
        minutes = self.remaining_time // 60
        seconds = self.remaining_time % 60
        self.close_button.setText(f"Schließen ({minutes:02d}:{seconds:02d})")

    def update_timer(self):
        self.remaining_time -= 1
        if self.remaining_time <= 0:
            self.auto_close_timer.stop()
            self.close()
        else:
            self.update_close_button()

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

    def closeEvent(self, event):
        self.auto_close_timer.stop()
        super().closeEvent(event)
