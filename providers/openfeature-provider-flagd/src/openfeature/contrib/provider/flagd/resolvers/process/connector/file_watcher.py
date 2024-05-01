import json
import logging
import os
import threading
import time
import typing

import yaml

from openfeature.evaluation_context import EvaluationContext
from openfeature.event import ProviderEventDetails
from openfeature.exception import ParseError, ProviderNotReadyError
from openfeature.provider.provider import AbstractProvider

from ..connector import FlagStateConnector
from ..flags import FlagStore

logger = logging.getLogger("openfeature.contrib")


class FileWatcher(FlagStateConnector):
    def __init__(
        self,
        file_path: str,
        provider: AbstractProvider,
        flag_store: FlagStore,
        poll_interval_seconds: float = 1.0,
    ):
        self.file_path = file_path
        self.provider = provider
        self.poll_interval_seconds = poll_interval_seconds

        self.last_modified = 0.0
        self.flag_store = flag_store
        self.emit_ready = False

    def initialize(self, evaluation_context: EvaluationContext) -> None:
        self.active = True
        self.thread = threading.Thread(target=self.refresh_file, daemon=True)
        self.thread.start()

        # Let this throw exceptions so that provider status is set correctly
        try:
            self._load_data()
            self.emit_ready = True
        except Exception as err:
            raise ProviderNotReadyError from err

    def shutdown(self) -> None:
        self.active = False

    def refresh_file(self) -> None:
        while self.active:
            time.sleep(self.poll_interval_seconds)
            logger.debug("checking for new flag store contents from file")
            last_modified = os.path.getmtime(self.file_path)
            if last_modified > self.last_modified:
                self.safe_load_data(last_modified)

    def safe_load_data(self, modified_time: typing.Optional[float] = None) -> None:
        try:
            self._load_data(modified_time)
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

    def _load_data(self, modified_time: typing.Optional[float] = None) -> None:
        with open(self.file_path) as file:
            if self.file_path.endswith(".yaml"):
                data = yaml.safe_load(file)
            else:
                data = json.load(file)

            self.flag_store.update(data)

            if self.emit_ready:
                self.provider.emit_provider_ready(
                    ProviderEventDetails(
                        message="Reloading file contents recovered from error state"
                    )
                )
                self.emit_ready = False

        self.last_modified = modified_time or os.path.getmtime(self.file_path)

    def handle_error(self, error_message: str) -> None:
        logger.exception(error_message)
        self.emit_ready = True
        self.provider.emit_provider_error(ProviderEventDetails(message=error_message))
