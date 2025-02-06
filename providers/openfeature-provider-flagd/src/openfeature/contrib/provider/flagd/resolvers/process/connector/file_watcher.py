import json
import logging
import os
import threading
import time
import typing

import yaml

from openfeature.contrib.provider.flagd.config import Config
from openfeature.contrib.provider.flagd.resolvers.process.connector import (
    FlagStateConnector,
)
from openfeature.contrib.provider.flagd.resolvers.process.flags import FlagStore
from openfeature.evaluation_context import EvaluationContext
from openfeature.event import ProviderEventDetails
from openfeature.exception import ParseError, ProviderNotReadyError

logger = logging.getLogger("openfeature.contrib")


class FileWatcher(FlagStateConnector):
    def __init__(
        self,
        config: Config,
        flag_store: FlagStore,
        emit_provider_ready: typing.Callable[[ProviderEventDetails], None],
        emit_provider_error: typing.Callable[[ProviderEventDetails], None],
    ):
        if config.offline_flag_source_path is None:
            raise ValueError(
                f"`config.offline_flag_source_path` parameter invalid: {config.offline_flag_source_path}"
            )
        else:
            self.file_path = config.offline_flag_source_path

        self.emit_provider_ready = emit_provider_ready
        self.emit_provider_error = emit_provider_error
        self.deadline_seconds = config.deadline_ms * 0.001

        self.last_modified = 0.0
        self.flag_store = flag_store
        self.should_emit_ready_on_success = False

    def initialize(self, evaluation_context: EvaluationContext) -> None:
        self.active = True
        self.thread = threading.Thread(
            target=self.refresh_file, daemon=True, name="FlagdFileWatcherWorkerThread"
        )
        self.thread.start()

        # Let this throw exceptions so that provider status is set correctly
        try:
            self.should_emit_ready_on_success = True
            self._load_data()
        except Exception as err:
            raise ProviderNotReadyError from err

    def shutdown(self) -> None:
        self.active = False

    def refresh_file(self) -> None:
        while self.active:
            time.sleep(self.deadline_seconds)
            logger.debug("checking for new flag store contents from file")
            self.safe_load_data()

    def safe_load_data(self) -> None:
        try:
            last_modified = os.path.getmtime(self.file_path)
            if last_modified > self.last_modified:
                self._load_data(last_modified)
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

            if self.should_emit_ready_on_success:
                self.emit_provider_ready(
                    ProviderEventDetails(
                        message="Reloading file contents recovered from error state"
                    )
                )
                self.should_emit_ready_on_success = False

        self.last_modified = modified_time or os.path.getmtime(self.file_path)

    def handle_error(self, error_message: str) -> None:
        logger.exception(error_message)
        self.should_emit_ready_on_success = True
        self.emit_provider_error(ProviderEventDetails(message=error_message))
