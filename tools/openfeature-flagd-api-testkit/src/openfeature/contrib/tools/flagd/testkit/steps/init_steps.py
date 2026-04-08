from pytest_bdd import given


@given("an evaluator")
def given_an_evaluator(evaluator):
    """Use the evaluator fixture provided by the consumer."""
    return evaluator
