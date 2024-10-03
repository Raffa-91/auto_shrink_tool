from PyQt5 import QtWidgets, QtGui
from logging_setup import main_logger
from dialogs import LogViewer, SettingsDialog

class SystemTrayIcon(QtWidgets.QSystemTrayIcon):
    def __init__(self, icon_path, parent=None):
        super().__init__(QtGui.QIcon(icon_path), parent)
        self.setToolTip('Auto DD Shrinker')
        self.menu = QtWidgets.QMenu(parent)

        status_action = self.menu.addAction('Shrink-Skript Status anzeigen')
        status_action.triggered.connect(self.show_status)

        logs_action = self.menu.addAction('Logs anzeigen')
        logs_action.triggered.connect(self.show_logs)

        settings_action = self.menu.addAction('Einstellungen öffnen')
        settings_action.triggered.connect(self.open_settings)

        quit_action = self.menu.addAction('Beenden')
        quit_action.triggered.connect(QtWidgets.qApp.quit)

        self.setContextMenu(self.menu)

    def show_status(self):
        QtWidgets.QMessageBox.information(None, 'Status', 'Das Shrink-Skript ist aktiv.')
        main_logger.debug("[TRAY] Status angezeigt.")

    def show_logs(self):
        self.log_viewer = LogViewer()
        self.log_viewer.show()
        main_logger.debug("[TRAY] Log Viewer geöffnet.")

    def open_settings(self):
        self.settings_dialog = SettingsDialog()
        self.settings_dialog.show()
        main_logger.debug("[TRAY] SettingsDialog geöffnet.")
