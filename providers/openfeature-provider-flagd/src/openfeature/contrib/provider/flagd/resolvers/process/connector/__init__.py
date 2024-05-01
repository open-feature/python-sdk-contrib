import typing

from openfeature.evaluation_context import EvaluationContext


class FlagStateConnector(typing.Protocol):
    def initialize(self, evaluation_context: EvaluationContext) -> None:
        pass

    def shutdown(self) -> None:
        pass
