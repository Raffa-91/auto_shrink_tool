import logging

class LogHandler:
    def __init__(self, log_file, level=logging.INFO):
        self.logger = logging.getLogger('main_logger')
        self.logger.setLevel(level)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)

    def info(self, message):
        self.logger.info(message)

    def error(self, message):
        self.logger.error(message)

# Beispiel für die Verwendung in deinem Hauptprogramm
# main_logger = LogHandler('main.log')
# main_logger.info('Programm gestartet')
