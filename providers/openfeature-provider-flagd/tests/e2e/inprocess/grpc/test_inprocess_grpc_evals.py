from pytest_bdd import scenarios

GHERKIN_FOLDER = "../../../../test-harness/gherkin/"

scenarios(f"{GHERKIN_FOLDER}flagd-json-evaluator.feature")
scenarios(f"{GHERKIN_FOLDER}flagd.feature")
