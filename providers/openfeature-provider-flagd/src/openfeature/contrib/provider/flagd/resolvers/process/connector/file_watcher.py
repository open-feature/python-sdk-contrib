import json
import logging
import os
import threading
import time
import typing

import yaml

from openfeature.event import ProviderEventDetails
from openfeature.exception import ParseError
from openfeature.provider.provider import AbstractProvider

from ..flags import Flag, FlagStore

logger = logging.getLogger("openfeature.contrib")


class FileWatcherFlagStore(FlagStore):
    def __init__(
        self,
        file_path: str,
        provider: AbstractProvider,
        poll_interval_seconds: float = 1.0,
    ):
        self.file_path = file_path
        self.provider = provider
        self.poll_interval_seconds = poll_interval_seconds

        self.last_modified = 0.0
        self.flag_data: typing.Mapping[str, Flag] = {}
        self.load_data()
        self.has_error = False
        self.thread = threading.Thread(target=self.refresh_file, daemon=True)
        self.thread.start()

    def shutdown(self) -> None:
        pass

    def get_flag(self, key: str) -> typing.Optional[Flag]:
        return self.flag_data.get(key)

    def refresh_file(self) -> None:
        while True:
            time.sleep(self.poll_interval_seconds)
            logger.debug("checking for new flag store contents from file")
            last_modified = os.path.getmtime(self.file_path)
            if last_modified > self.last_modified:
                self.load_data(last_modified)

    def load_data(self, modified_time: typing.Optional[float] = None) -> None:
        try:
            with open(self.file_path) as file:
                if self.file_path.endswith(".yaml"):
                    data = yaml.safe_load(file)
                else:
                    data = json.load(file)

                self.flag_data = Flag.parse_flags(data)
                logger.debug(f"{self.flag_data=}")

                if self.has_error:
                    self.provider.emit_provider_ready(
                        ProviderEventDetails(
                            message="Reloading file contents recovered from error state"
                        )
                    )
                    self.has_error = False

                self.provider.emit_provider_configuration_changed(
                    ProviderEventDetails(flags_changed=list(self.flag_data.keys()))
                )
            self.last_modified = modified_time or os.path.getmtime(self.file_path)
        except FileNotFoundError:
            self.handle_error("Provided file path not valid")
        except json.JSONDecodeError:
            self.handle_error("Could not parse JSON flag data from file")
        except yaml.error.YAMLError:
            self.handle_error("Could not parse YAML flag data from file")
        except ParseError:
            self.handle_error("Could not parse flag data using flagd syntax")
        except Exception:
            self.handle_error("Could not read flags from file")

    def handle_error(self, error_message: str) -> None:
        logger.exception(error_message)
        self.has_error = True
        self.provider.emit_provider_error(ProviderEventDetails(message=error_message))
