from pytest_bdd import scenarios

from openfeature.contrib.tools.flagd.testkit import get_features_path

scenarios(get_features_path())
