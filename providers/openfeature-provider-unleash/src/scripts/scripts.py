# ruff: noqa: S602, S607
import subprocess


def test() -> None:
    """Run pytest tests."""
    subprocess.run("pytest tests", shell=True, check=True)


def test_cov() -> None:
    """Run tests with coverage."""
    subprocess.run("coverage run -m pytest tests", shell=True, check=True)


def cov_report() -> None:
    """Generate coverage report."""
    subprocess.run("coverage xml", shell=True, check=True)


def cov() -> None:
    """Run tests with coverage and generate report."""
    test_cov()
    cov_report()


def mypy() -> None:
    """Run mypy."""
    subprocess.run("mypy", shell=True, check=True)


def lint() -> None:
    """Run ruff linting."""
    subprocess.run("ruff check", shell=True, check=True)
