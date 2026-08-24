"""The shared step vocabulary.

Each module here is registered as a pytest plugin by the TCK's own plugin, which
is what makes the steps visible: pytest-bdd's decorators inject a generated
fixture name into the *defining* module's namespace, so a step only reaches
pytest once its module is a registered plugin.

Deliberately empty of imports. Pulling the submodules in here would import them
before pytest loads them as plugins, and pytest cannot rewrite assertions in a
module that is already imported.
"""
