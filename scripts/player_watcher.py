import argparse
import json
import os
import time
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


def parse_player_file(path):
    data = {}
    try:
        with open(path, "r", encoding="latin-1") as file:
            for line in file:
                line = line.strip()
                if not line or ":" not in line:
                    continue
                key, value = line.split(":", 1)
                data[key.strip()] = value.strip()
    except (OSError, UnicodeDecodeError) as exc:
        print(f"Failed to read {path}: {exc}")
        return None
    return data


class PlayerFileHandler(FileSystemEventHandler):
    def __init__(self, player_dir):
        super().__init__()
        self.player_dir = os.path.abspath(player_dir)

    def on_modified(self, event):
        if event.is_directory:
            return
        if not os.path.abspath(event.src_path).startswith(self.player_dir):
            return

        parsed = parse_player_file(event.src_path)
        if parsed is not None:
            print(json.dumps(parsed))


def main():
    parser = argparse.ArgumentParser(description="Watch player files and emit JSON on changes.")
    parser.add_argument(
        "player_dir",
        nargs="?",
        default=os.path.join(os.path.dirname(__file__), "..", "player"),
        help="Directory containing player save files (default: ../player)",
    )
    args = parser.parse_args()

    player_dir = os.path.abspath(args.player_dir)
    if not os.path.isdir(player_dir):
        raise SystemExit(f"Player directory not found: {player_dir}")

    event_handler = PlayerFileHandler(player_dir)
    observer = Observer()
    observer.schedule(event_handler, path=player_dir, recursive=False)
    observer.start()

    print(f"Watching {player_dir} for modifications...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping watcher.")
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()
