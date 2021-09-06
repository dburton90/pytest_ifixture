import pytest


def test_session(base_session):
    tests = [t.test.name for t in base_session.tests]
    assert tests == ['test_articles', 'test_db[dogs]', 'test_db[cats]']


def test_get_test_by_name(base_session):
    # non existing test raise error
    with(pytest.raises(ValueError)):
        base_session.get_test_by_name('non existing')

    test = base_session.get_test_by_name('test_articles')
    assert test.test.name == 'test_articles'


def test_get_tests_by_fixture(base_session):
    tests = base_session.get_tests_for_fixture('author')
    assert len(tests) == 1
    assert tests[0].test.name == 'test_articles'

    tests = base_session.get_tests_for_fixture('db')
    assert len(tests) == 3


def test_active_test(base_session):
    test = base_session.get_test_by_name('test_articles')

    assert base_session.active_test is None

    test.getfixturevalue('db_name')

    assert base_session.active_test is not None
    assert base_session.active_test.test.name == 'test_articles'


def test_can_be_used_and_active(base_session):

    assert all([t.can_be_used for t in base_session.tests])
    assert not any([t.active for t in base_session.tests])

    article = base_session.get_test_by_name('test_articles')
    db_cats = base_session.get_test_by_name('test_db[dogs]')
    db_dogs = base_session.get_test_by_name('test_db[cats]')
    article.getfixturevalue('db_name')

    assert article.can_be_used
    assert article.active

    assert not db_cats.can_be_used
    assert not db_cats.active
    assert not db_dogs.can_be_used
    assert not db_dogs.active

    article.reset()

    assert all([t.can_be_used for t in base_session.tests])
    assert not any([t.active for t in base_session.tests])

