# V0.1a/log_handler.py
import logging
import os

# Erstellen eines zentralen Loggers
logger = logging.getLogger('auto_dd_shrinker')
logger.setLevel(logging.DEBUG)  # Setzen des gewünschten Log-Levels

# Erstellen von Handlers (Konsole und Log-Datei)
console_handler = logging.StreamHandler()
log_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'autodds_monitor.log')
file_handler = logging.FileHandler(log_file_path)

console_handler.setLevel(logging.DEBUG)
file_handler.setLevel(logging.DEBUG)

# Definieren eines Log-Formats
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

# Hinzufügen der Handler zum Logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)
