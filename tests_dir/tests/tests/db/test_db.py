import pytest
from articles.logger import log_setup, log_teardown


@pytest.fixture
def db_name():
    log_setup(db_name)
    yield db_name.__name__ + '-2'
    log_teardown(db_name)


@pytest.fixture
def article(article, db):
    log_setup(article, db)
    yield article + '-overridden-addition'
    log_teardown(article, db)


def test_db(article, request):
    log_setup(test_db, article)
    request.addfinalizer(lambda: log_teardown(test_db, article))


