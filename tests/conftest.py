from pathlib import Path

import pytest

BASE_DIR = Path(__file__).parent.parent
TEST_DIR = BASE_DIR.joinpath('tests_dir')


@pytest.fixture(autouse=True)
def ses(monkeypatch):
    monkeypatch.chdir(TEST_DIR)
    monkeypatch.syspath_prepend(BASE_DIR.joinpath('src'))  # pytest_ifixture
    monkeypatch.syspath_prepend(BASE_DIR.joinpath('test_dir', 'project'))  # articles.logger


@pytest.fixture
def base_session():
    import pytest_ifixture as pi
    s = pi.get_session()
    yield s
    s.cleanup_session()


@pytest.fixture
def article_logger(monkeypatch):
    from articles import logger
    monkeypatch.setattr(logger, 'LOGGER', [])
    return logger.LOGGER

