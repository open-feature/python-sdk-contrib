import json
import logging
import os
import threading
import time
import typing


class FileWatcherFlagStore:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.last_modified = 0.0
        self.load_data()
        self.thread = threading.Thread(target=self.refresh_file, daemon=True)
        self.thread.start()

    def shutdown(self) -> None:
        pass

    def get_flag(self, key: str) -> typing.Optional[dict]:
        return self.flag_data.get(key)

    def refresh_file(self) -> None:
        while True:
            time.sleep(1)
            logging.debug("checking for new flag store contents from file")
            last_modified = os.path.getmtime(self.file_path)
            if last_modified > self.last_modified:
                self.load_data(last_modified)

    def load_data(self, modified_time: typing.Optional[float] = None) -> None:
        # TODO: error handling
        with open(self.file_path) as file:
            self.flag_data: dict = json.load(file).get("flags", {})
            logging.debug(f"{self.flag_data=}")
        self.last_modified = modified_time or os.path.getmtime(self.file_path)
