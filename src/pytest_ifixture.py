import inspect
import sys
import traceback
from collections import namedtuple

import pytest
from _pytest import config, main

import atexit

from _pytest.fixtures import FixtureDef


def get_session(args=None, pytest_cmdlines=None):
    """
    Create session handler for handling tests and fixtures interactively.
    This will prepare session same way as it is classic testing pytest session.

    WARNING:
    hooks PYTEST_CMDLINE_MAIN are skipped, since implementation of this hook is responsible for running the tests,
    we can't run this hook. If you have some custom setup used in this hook, you can provide it in list in parameter
    pytest_cmdlines.

    :param args: same list of arguments passed to the pytest for testing
    :param pytest_cmdlines: list of commands running with pytest config object, before creating session
    :return: PytestSession
    """
    pytest_cmdlines = pytest_cmdlines or []
    args = args or []
    args.append('-s')
    plugins = None

    # config.main
    conf = config._prepareconfig(args, plugins)

    for pcmd in pytest_cmdlines:
        pcmd(conf)

    # main.wrap_session
    try:
        session = main.Session.from_config(config=conf)
    except AttributeError:
        session = main.Session(conf)

    cleanup = lambda: cleanup_config(conf, session)
    atexit.register(cleanup)

    try:
        conf._do_configure()
        conf.hook.pytest_sessionstart(session=session)
        conf.hook.pytest_collection(session=session)
    except:
        cleanup()
        raise

    return PytestSession(session, conf, cleanup)


class PytestSession(namedtuple('PytestSession', 'session, config, cleanup_session')):
    """
    This hold pytest session and provide some api for it.

    There should be only one active test at the same time.
    Active test is test with at least one resolved fixture.
    To use other test, current session must be teardowned.

    session: pytest session
    config: pytest config for this session
    cleanup_session: teardown fixtures, cleanup session and config
    """
    __slots__ = ()

    @property
    def tests(self):
        """ List of all tests in this session. """
        return [PytestTest(t, self) for t in self.session.items]

    @property
    def config(self):
        return self.config.options

    def get_test_by_name(self, test):
        """ Retrieve test by name."""
        try:
            test = [t for t in self.session.items if t.name == test][0]
        except IndexError:
            raise ValueError(f"Test '{test}' does not exists.")
        if self.active_test and self.active_test != test:
            raise ValueError(f"You can't use test {test.name}, because you did not finalize currently active test.")
        return PytestTest(test, self)

    def get_tests_for_fixture(self, fixture):
        """ Get all tests using fixture with this name. """
        tests = []
        for test in self.session.items:
            if fixture in test.fixturenames:
                tests.append(test)
        return [PytestTest(t, self) for t in tests]

    @property
    def active_test(self):
        """ Return active test (test with at least resolved fixture). Return None if there is no active test."""
        finalizers = self.session._setupstate._finalizers
        if finalizers:
            return PytestTest(list(finalizers.keys())[0], self)

    def teardown(self):
        """ Teardown whole session."""
        self.session._setupstate.teardown_all()


class PytestTest(namedtuple('PytestTest', 'test, pytestsession')):
    """
    This hold pytest test (item). It is used to create fixture.
    """
    __slots__ = ()

    @property
    def fixtures(self):
        """ All fixture names. """
        return self.test.fixturenames

    @property
    def fixture_values(self):
        """ Dict with resolved fixtures mapped to their values. """
        fixture_values = {}
        for f in self.fixtures:
            if f in self.request._fixture_defs:
                fdef = self.request._fixture_defs[f]
                fixture_values[f] = fdef.cached_result[0]

        return fixture_values

    @property
    def fixtures_unresolved(self):
        """ List of unresolved fixtures. """
        fixtures = []
        for f in self.fixtures:
            if f not in self.request._fixture_defs:
                fixtures.append(f)

        return fixtures

    @property
    def request(self):
        """ pytest request for this test """
        return self.test._request

    @property
    def active(self):
        """ check if this test is active """
        return self.pytestsession.active_test == self

    @property
    def can_be_used(self):
        """ check if we can get fixture for this test (no other test in this session is active) """
        current_test = self.pytestsession.active_test
        return current_test is None or current_test == self

    @property
    def session(self):
        """ Pytest session."""
        return self.request.session

    def reset(self, remove_custom_fixtures=False):
        """
        Reset (teardown) all fixtures. Optionally remove all fixtures added with setfixture method.
        """
        self.request._arg2index = {}
        self.request._fixture_defs = {}
        self.session._setupstate.teardown_all()
        if remove_custom_fixtures:
            self.request._arg2fixturedefs = self.test._fixtureinfo.name2fixturedefs.copy()

    def reset_fixture(self, fixture):
        """
        Reset only specific fixture (and all fixtures depending on it).

        :param fixture: name of the fixture
        :return:
        """
        fixture_cleanups = self.session._setupstate._finalizers[self.test]

        def get_fixture_name_from_cleanup_method(method):
            try:
                return method.func.__self__.argname
            except KeyError:
                return object()

        fixture_names = list(map(get_fixture_name_from_cleanup_method, fixture_cleanups))

        try:
            index = fixture_names.index(fixture)
        except KeyError:
            raise KeyError(f"Can't find {fixture} in {fixture_names}")

        fixture_cleanups = list(zip(fixture_names[index:], fixture_cleanups[index:]))
        exceptions = []
        while fixture_cleanups:
            name, finish = fixture_cleanups.pop()
            try:
                finish()
            except Exception:
                exceptions.append((name, sys.exc_info()))
            finally:
                self.request._arg2index.pop(name, None)
                self.request._fixture_defs.pop(name, None)

        for e in exceptions:
            name, exc = e
            print(f"ERROR IN TEARDOWN FIXTURE [{name}]:")
            traceback.print_exception(*exc)

    def getfixturevalue(self, fixture):
        """
        Retrieve fixture value for this test. Check if this no other test is active in this session.

        If fixture setup throws Exception, the setup will NOT be rolled back, and you need to do it manually.
        """
        if not self.can_be_used:
            raise ValueError("Can't get fixture value. Other test is active.")
        return self.request.getfixturevalue(fixture)

    def setfixture(self, fixture, value):
        """
        Add fixture to the test.
        - It can override some fixture or create new fixture (not even related to this test).
        - Check if no other test is active.
        - Check if the fixture is not already resolved.

        :param fixture: name of the fixture
        :param value:
            - fixture (method decorated with @pytest.fixture)
            - callable (function should return fixture value)
            - any other (will be used as returned value for the fixture)
        """
        if not self.can_be_used:
            raise ValueError("Can't set fixture value. Other test is active.")
        if fixture in self.request._fixture_defs:
            raise ValueError("Fixture is already set.")
        add_fixture_to_test(fixture, value, self.request)

    def print_fixtures(self, fixtures=None):
        """ print all fixtures in this test. """
        if fixtures:
            if isinstance(fixtures, str):
                fixtures = [fixtures]
        else:
            fixtures = self.fixtures

        for f in fixtures:
            fixturedefs = self.test._fixtureinfo.name2fixturedefs.get(f, None)
            if fixturedefs is None:
                continue
            print(f)
            for fd in fixturedefs:
                print(' ' * 2 + fd.baseid)
                try:
                    print(*map(lambda s: ' ' * 4 + s, inspect.getsource(fd.func).splitlines()), sep='\n')
                except OSError:
                    print(f"{' '*4}COULD NOT FIND CODE FOR {fd.baseid}")
            print()

    def __repr__(self):
        return f"<PytestTest {self.test.name}{' (active)' if self.active else ''}>"

    def __str__(self):
        return self.test.baseid

    def __eq__(self, other):
        return isinstance(other, self.__class__) and other.test == self.test and other.session is self.session


def add_fixture_to_test(fixture_name, fixture, request):
    """
    Replace last FixtureDef for fixture_name in request._arg2fixturedefs
    :param fixture_name: str
    :param fixture: [Value, Func, Fixture]
    :param request: FixtureRequest
    :return:
    """
    fixture_value, fixture_function, decorated_fixture = None, None, None
    if callable(fixture):
        fixture_function = fixture
    else:
        fixture_value = fixture
        fixture_function = lambda: fixture_value

    if hasattr(fixture_function, '_pytestfixturefunction'):
        print('is fixture')
        decorated_fixture = fixture_function
        fixture_function = decorated_fixture.__wrapped__
    else:
        print('is not fixture')
        decorated_fixture = pytest.fixture(fixture_function)

    marker = decorated_fixture._pytestfixturefunction
    fixture_def = FixtureDef(
        fixturemanager=request._fixturemanager,
        baseid='',
        argname=fixture_name,
        func=fixture_function,
        scope=marker.scope,
        params=marker.params,
        unittest=False,
        ids=marker.ids
    )
    request._arg2fixturedefs[fixture_name] = (*request._arg2fixturedefs.get(fixture_name, [])[:-1], fixture_def)


def cleanup_config(config, session):
    try:
        session._setupstate.teardown_all()
    except Exception as exc:
        sys.stderr.write('{}: {}\n'.format(type(exc).__name__, exc))
    try:
        config.hook.pytest_sessionfinish(session=session, exitstatus=session.exitstatus)
    except Exception as exc:
        sys.stderr.write('{}: {}\n'.format(type(exc).__name__, exc))
    config._ensure_unconfigure()


