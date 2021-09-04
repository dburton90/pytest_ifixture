import pytest
from articles.logger import log_setup, log_teardown


@pytest.fixture
def article(db):
    log_setup(article, db)
    yield article.__name__ + '-overridden-full'
    log_teardown(article, db)


def test_articles(article, request):
    request.addfinalizer(lambda:log_teardown(article))
    log_setup(article)
