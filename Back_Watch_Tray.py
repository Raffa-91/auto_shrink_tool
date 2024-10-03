import sys
import subprocess
from pystray import Icon, MenuItem as item, Menu
from PIL import Image
import threading
import time
import os
import re
import tkinter as tk
from tkinter import messagebox, ttk

# Funktion, um das Shrink-Script anzuzeigen (zum Testen geben wir nur eine Meldung aus)
def show_shrink_status(icon, item):
    print("Zeige Shrink-Script-Status an")
    subprocess.call(['lxterminal', '-e', 'echo Shrink-Script läuft'])

# Funktion, um die Logs des letzten Backups anzuzeigen
def show_logs(icon, item):
    print("Zeige Logs des letzten Backups an")
    subprocess.call(['lxterminal', '-e', 'echo Zeige Backup-Logs'])

# Funktion, um die Einstellungen zu öffnen
def show_settings(icon, item):
    print("Öffne die Einstellungen")
    subprocess.call(['lxterminal', '-e', 'echo Einstellungen öffnen'])

# Funktion, um das Programm zu beenden
def quit_program(icon, item):
    print("Beende das Programm")
    icon.stop()

# Funktion, die prüft, ob eine Datei seit 1 Minute nicht benutzt wird
def is_file_unused(filepath):
    current_time = time.time()
    last_modification_time = os.path.getmtime(filepath)
    return (current_time - last_modification_time) > 60  # Datei wurde in den letzten 60 Sekunden nicht geändert

# Funktion, um den jüngsten Backup-Ordner zu finden
def get_latest_backup_folder(backup_directory, folder_pattern):
    latest_folder = None
    latest_time = 0

    for folder in os.listdir(backup_directory):
        folder_path = os.path.join(backup_directory, folder)

        # Prüfe, ob der Ordner dem Muster entspricht und ob er ein Verzeichnis ist
        if os.path.isdir(folder_path) and folder_pattern.match(folder):
            folder_creation_time = os.path.getmtime(folder_path)

            if folder_creation_time > latest_time:
                latest_time = folder_creation_time
                latest_folder = folder_path

    return latest_folder

# Funktion, um das pishrink.sh-Skript auszuführen
def run_pishrink_script(img_file, command):
    pishrink_script_path = os.path.join(os.path.dirname(__file__), 'pishrink.sh')
    
    # Überprüfe, ob das pishrink.sh-Skript existiert
    if not os.path.exists(pishrink_script_path):
        print(f"pishrink.sh-Skript wurde nicht gefunden unter: {pishrink_script_path}")
        return

    # Bestätigungsdialog mit Tkinter
    root = tk.Tk()
    root.withdraw()  # Versteckt das Hauptfenster

    result = messagebox.askyesno("Bestätigung", f"Möchtest du den folgenden Befehl ausführen?\n\n{command}")
    root.destroy()  # Zerstöre das Fenster, nachdem die Auswahl getroffen wurde

    if result:  # Wenn der Benutzer "Ja" bestätigt
        print(f"Führe Befehl aus: {command}")
        
        try:
            # Führe den Befehl im Terminal aus und halte das Terminal offen
            subprocess.call(['lxterminal', '--command', f'bash -c "{command}; read -p \'Press Enter to close...\'"'])
        except Exception as e:
            print(f"Fehler beim Ausführen des Befehls: {e}")
    else:
        print("Befehlsausführung abgebrochen.")

# GUI für die Eingabe von Befehlen und Auswahl von Attributen
def open_command_gui(img_file):
    root = tk.Tk()
    root.title("Shrink-Skript-Ausführung")
    root.geometry("450x250")  # Verkleinerte Größe der GUI
    
    # Standardbefehl
    pishrink_script_path = os.path.join(os.path.dirname(__file__), 'pishrink.sh')
    default_command = f"sudo bash {pishrink_script_path} {img_file}"
    
    # Eingabefeld für den Befehl
    command_label = ttk.Label(root, text="Befehl:")
    command_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
    
    command_entry = tk.Entry(root, width=50)
    command_entry.insert(0, default_command)
    command_entry.grid(row=0, column=1, padx=5, pady=5)

    # Vorschau für Beschreibungen
    description_label = ttk.Label(root, text="Attribut Beschreibung:")
    description_label.grid(row=1, column=0, padx=5, pady=5, sticky="nw")
    
    description_box = tk.Text(root, height=4, width=30, wrap="word", state="disabled", relief="flat")
    description_box.grid(row=1, column=1, padx=5, pady=5)

    # Funktion zum Ändern der Beschreibung
    def update_description(text):
        description_box.config(state="normal")
        description_box.delete(1.0, tk.END)
        description_box.insert(tk.END, text)
        description_box.config(state="disabled")

    # Checkboxen für Attribute
    def create_checkbox(text, command_flag, description):
        var = tk.BooleanVar()
        chk = tk.Checkbutton(root, text=text, variable=var)
        chk.grid(sticky="w", padx=5)
        chk.bind("<Enter>", lambda event: update_description(description))
        return var, command_flag

    # Checkboxen und deren Beschreibungen
    attr_a, flag_a = create_checkbox("-a (Automatischer Modus)", "-a", "Führt die Operation automatisch ohne Benutzerinteraktion aus.")
    attr_r, flag_r = create_checkbox("-r (Entfernen)", "-r", "Entfernt temporäre Dateien nach der Ausführung.")
    attr_s, flag_s = create_checkbox("-s (Simulation)", "-s", "Führt keine Änderungen durch, zeigt nur, was passieren würde.")
    attr_v, flag_v = create_checkbox("-v (Verbose)", "-v", "Zeigt detaillierte Ausgaben während der Ausführung.")
    
    # Funktion, um den Befehl zu aktualisieren
    def update_command():
        command = default_command
        if attr_a.get():
            command += f" {flag_a}"
        if attr_r.get():
            command += f" {flag_r}"
        if attr_s.get():
            command += f" {flag_s}"
        if attr_v.get():
            command += f" {flag_v}"
        command_entry.delete(0, tk.END)
        command_entry.insert(0, command)

    # Button zum Ausführen des Befehls
    def execute_command():
        command = command_entry.get()
        root.destroy()  # Schließt das Fenster nach Bestätigung
        run_pishrink_script(img_file, command)

    # Button zum Bestätigen des Befehls
    confirm_button = ttk.Button(root, text="Bestätigen", command=execute_command)
    confirm_button.grid(row=2, column=1, pady=10)

    root.mainloop()

# Hintergrundfunktion, um den Hauptordner zu überwachen
def background_task():
    # Der Hauptordner, in dem neue Backup-Ordner erstellt werden
    backup_directory = '/media/raphi/hdd/backups/raspiHauptDD/raspihaupt/'
    
    # Muster für die neuen Backup-Ordner "raspihaupt-dd-backup-\d{8}-\d{6}"
    folder_pattern = re.compile(r'raspihaupt-dd-backup-\d{8}-\d{6}')

    while True:
        print("Überwache Backup-Ordner...")

        try:
            # Finde den jüngsten Backup-Ordner
            latest_folder = get_latest_backup_folder(backup_directory, folder_pattern)

            if latest_folder:
                print(f"Untersuche neuesten Backup-Ordner: {latest_folder}")

                # Prüfe, ob eine IMG-Datei existiert
                for file in os.listdir(latest_folder):
                    if file.endswith('.img'):
                        img_file_path = os.path.join(latest_folder, file)
                        print(f"Gefundene IMG-Datei: {img_file_path}")

                        # Prüfe, ob die Datei seit 1 Minute nicht mehr benutzt wird
                        if is_file_unused(img_file_path):
                            print(f"IMG-Datei ist unbenutzt: {img_file_path}")
                            # Öffne GUI für Befehlseingabe und Attribute
                            open_command_gui(img_file_path)
                        else:
                            print(f"IMG-Datei wird noch benutzt: {img_file_path}")
            else:
                print("Kein neuer Backup-Ordner gefunden.")
        except Exception as e:
            print(f"Fehler bei der Ordnerüberwachung: {e}")

        # Alle 10 Minuten überprüfen
        time.sleep(600)

# Hauptprogramm
def setup_tray():
    # Lade das Icon von einer PNG-Datei
    icon_image_path = os.path.join(os.path.dirname(__file__), "icon.png")  # Stelle sicher, dass icon.png existiert

    if not os.path.exists(icon_image_path):
        print(f"Das Icon wurde nicht gefunden unter: {icon_image_path}")
        sys.exit(1)

    icon_image = Image.open(icon_image_path)

    # Erstelle das Tray-Icon
    icon = Icon("backup_tray", icon_image)

    # Menü im Tray erstellen
    icon.menu = Menu(
        item('Shrink-Script Status anzeigen', show_shrink_status),
        item('Backup Logs anzeigen', show_logs),
        item('Einstellungen öffnen', show_settings),
        item('Beenden', quit_program)
    )

    # Tray-Icon starten
    icon.run()

if __name__ == "__main__":
    # Hintergrundüberwachung als separaten Thread starten
    bg_thread = threading.Thread(target=background_task, daemon=True)
    bg_thread.start()

    # Tray-Icon einrichten
    setup_tray()
