import pytest


def test_get_fixture(base_session, article_logger):
    test = base_session.get_test_by_name('test_articles')
    test.getfixturevalue('db_name')

    assert article_logger == ['SETUP: conftest.db_name']


def test_teardown(base_session, article_logger):
    test = base_session.get_test_by_name('test_articles')
    test.getfixturevalue('db_name')
    test.reset()

    assert article_logger == ['SETUP: conftest.db_name', 'TEARDOWN: conftest.db_name']


def test_get_fixture_repeatedly(base_session, article_logger):
    test = base_session.get_test_by_name('test_articles')
    test.getfixturevalue('db_name')
    test.reset()
    test.getfixturevalue('db_name')

    assert article_logger == [
        'SETUP: conftest.db_name',
        'TEARDOWN: conftest.db_name',
        'SETUP: conftest.db_name',
    ]



def test_get_fixture_depends_on_each_other(base_session, article_logger):
    test = base_session.get_test_by_name('test_db[cats]')
    test.getfixturevalue('article_new')

    assert article_logger == [
        'SETUP: test_db.db_name',
        'SETUP: conftest.db db_name-2',
        "SETUP: conftest.article cats,db(db_name-2),<SubRequest 'article' for <Function test_db[cats]>>",
        "SETUP: conftest.article cats,db(db_name-2),<SubRequest 'article' for <Function test_db[cats]>>",
        'SETUP: articlecats db(db_name-2)',
    ]


def test_teardown_fixture_depends_on_each_other(base_session, article_logger):
    test = base_session.get_test_by_name('test_db[cats]')
    test.getfixturevalue('article_new')
    test.reset()
    assert article_logger == [
        'SETUP: test_db.db_name',
        'SETUP: conftest.db db_name-2',
        "SETUP: conftest.article cats,db(db_name-2),<SubRequest 'article' for <Function test_db[cats]>>",
        "SETUP: conftest.article cats,db(db_name-2),<SubRequest 'article' for <Function test_db[cats]>>",
        'SETUP: articlecats db(db_name-2)',

        'TEARDOWN: articlecats db(db_name-2)',
        "TEARDOWN: conftest.article cats,db(db_name-2),<SubRequest 'article' for <Function test_db[cats]>>",
        "TEARDOWN: conftest.article cats,db(db_name-2),<SubRequest 'article' for <Function test_db[cats]>>",

        'TEARDOWN: conftest.db db_name-2',
        'TEARDOWN: test_db.db_name',
    ]


def test_partial_teardown(base_session, article_logger):
    test = base_session.get_test_by_name('test_db[cats]')
    test.getfixturevalue('article_new')
    test.reset_fixture('article')
    assert article_logger == [
        'SETUP: test_db.db_name',
        'SETUP: conftest.db db_name-2',
        "SETUP: conftest.article cats,db(db_name-2),<SubRequest 'article' for <Function test_db[cats]>>",
        "SETUP: conftest.article cats,db(db_name-2),<SubRequest 'article' for <Function test_db[cats]>>",
        'SETUP: articlecats db(db_name-2)',

        'TEARDOWN: articlecats db(db_name-2)',
        "TEARDOWN: conftest.article cats,db(db_name-2),<SubRequest 'article' for <Function test_db[cats]>>",
        "TEARDOWN: conftest.article cats,db(db_name-2),<SubRequest 'article' for <Function test_db[cats]>>",
    ]


def test_cant_set_custom_fixture(base_session):
    test = base_session.get_test_by_name('test_articles')
    db = test.getfixturevalue('db')
    assert db == 'db(db_name)'

    with pytest.raises(ValueError):
        test.setfixture('db_name', '')


def test_set_fixture_value_by_str(base_session):
    test = base_session.get_test_by_name('test_articles')
    test.setfixture('db_name', 'new name')
    db = test.getfixturevalue('db')
    assert db == 'db(new name)'


def test_set_fixture_value_by_callable(base_session):
    test = base_session.get_test_by_name('test_articles')
    def set_f():
        return 'new name'
    test.setfixture('db_name', set_f)
    db = test.getfixturevalue('db')
    assert db == 'db(new name)'


def test_set_fixture_value_by_fixture(base_session):
    test = base_session.get_test_by_name('test_articles')

    teardown_f = False

    @pytest.fixture
    def set_f():
        nonlocal teardown_f
        yield 'new name'
        teardown_f = True

    test.setfixture('db_name', set_f)

    db = test.getfixturevalue('db')
    assert db == 'db(new name)'

    assert teardown_f is False

    test.reset()

    assert teardown_f is True


def test_set_non_related_fixture(base_session):
    test = base_session.get_test_by_name('test_articles')
    teardown_f = False

    @pytest.fixture
    def set_f(db_name):
        nonlocal teardown_f
        yield db_name + ' + new fixture'
        teardown_f = True


    test.setfixture('new_fixture', set_f)

    db = test.getfixturevalue('new_fixture')
    assert db == 'db_name + new fixture'

    assert teardown_f is False

    test.reset()

    assert teardown_f is True


def test_values(base_session):
    test = base_session.get_test_by_name('test_articles')
    db = test.getfixturevalue('db')
    assert test.fixture_values == {
        'db_name': 'db_name',
        'db': 'db(db_name)'
    }
    test.reset()
    assert test.fixture_values == {}


def test_unresolved(base_session):
    test = base_session.get_test_by_name('test_articles')
    db = test.getfixturevalue('db')
    assert test.fixtures_unresolved.sort() == ['article', 'author'].sort()
