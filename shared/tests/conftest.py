import pytest


@pytest.fixture(scope="session")
def test_db_name() -> str:
    return "test_ads_db"


@pytest.fixture(scope="session")
def test_db_user() -> str:
    return "test_user"


@pytest.fixture(scope="session")
def test_db_password() -> str:
    return "test_password"


@pytest.fixture(scope="session")
def test_db_port() -> int:
    return 5432
