from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time

class TestEventHandler(FileSystemEventHandler):
    def on_created(self, event):
        print(f"Erstellt: {event.src_path}")

if __name__ == "__main__":
    path = "/media/raphi/hdd/backups/raspiHauptDD/raspihaupt"
    event_handler = TestEventHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
