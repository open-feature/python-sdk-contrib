import json
import logging
import os
import re
import threading
import time
import typing

from openfeature.event import ProviderEventDetails
from openfeature.provider.provider import AbstractProvider


class FileWatcherFlagStore:
    def __init__(self, file_path: str, provider: AbstractProvider):
        self.file_path = file_path
        self.provider = provider
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
            self.flag_data: dict = self.parse_flags(json.load(file))
            logging.debug(f"{self.flag_data=}")
            self.provider.emit_provider_configuration_changed(
                ProviderEventDetails(flags_changed=list(self.flag_data.keys()))
            )
        self.last_modified = modified_time or os.path.getmtime(self.file_path)

    def parse_flags(self, flags_data: dict) -> dict:
        flags = flags_data.get("flags", {})
        evaluators: typing.Optional[dict] = flags_data.get("$evaluators")
        if evaluators:
            transposed = json.dumps(flags)
            for name, rule in evaluators.items():
                transposed = re.sub(
                    rf"{{\s*\"\$ref\":\s*\"{name}\"\s*}}", json.dumps(rule), transposed
                )
            flags = json.loads(transposed)

        if not isinstance(flags, dict):
            raise ValueError("`flags` key of configuration must be a dictionary")
        return flags
