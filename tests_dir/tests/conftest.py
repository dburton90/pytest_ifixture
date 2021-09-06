import pytest
from articles.logger import log_setup, log_teardown

pytestmark = [pytest.mark.parametrize('title', ['dogs', 'cats'])]

@pytest.fixture
def db_name():
    log_setup(db_name)
    yield db_name.__name__
    log_teardown(db_name)


@pytest.fixture
def db(db_name):
    log_setup(db, db_name)
    yield f'{db.__name__}({db_name})'
    log_teardown(db, db_name)


@pytest.fixture(params=['dogs', 'cats'])
def article(db, request):
    title = request.param
    log_setup(article, title, db, request)
    log_setup(article, title, db, request)
    request.addfinalizer(lambda: log_teardown(article, title, db, request))
    request.addfinalizer(lambda: log_teardown(article, title, db, request))
    return article.__name__ + title


