import typing

from pytest_bdd import given

from openfeature.contrib.tools.flagd.api import Evaluator


@given("an evaluator")
def given_an_evaluator(evaluator: Evaluator) -> typing.Any:
    """Use the evaluator fixture provided by the consumer."""
    return evaluator
