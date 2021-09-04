import inspect
import sys
from collections import namedtuple
from typing import Union

import pytest
from _pytest import config, main

import atexit

from _pytest.compat import get_real_func
from _pytest.fixtures import FixtureDef


class PytestSession(namedtuple('PytestSession', 'session, config, cleanup_session')):
    __slots__ = ()

    @property
    def tests(self):
        return [PytestTest(t, self) for t in self.session.items]

    def get_test_by_name(self, test):
        try:
            test = [t for t in self.session.items if t.name == test][0]
        except IndexError:
            raise ValueError(f"Test '{test}' does not exists.")
        if self.current_test and self.current_test != test:
            raise ValueError(f"You can't use test {test.name}, because you did not finalize currently active test.")
        return PytestTest(test, self)

    def get_tests_for_fixture(self, fixture):
        tests = []
        for test in self.session.items:
            if fixture in test.fixturenames:
                tests.append(test)
        return [PytestTest(t, self) for t in tests]

    @property
    def current_test(self):
        finalizers = self.session._setupstate._finalizers
        if finalizers:
            return PytestTest(list(finalizers.keys())[0], self)

    def teardown(self):
        self.session._setupstate.teardown_all()


class PytestTest(namedtuple('PytestTest', 'test, pytestsession')):
    __slots__ = ()

    @property
    def fixtures(self):
        return self.test.fixturenames

    @property
    def request(self):
        return self.test._request

    @property
    def can_be_used(self):
        current_test = self.pytestsession.current_test
        return current_test is None or current_test == self

    @property
    def session(self):
        return self.request.session

    def reset(self):
        self.session._setupstate.teardown_all()
        self.request._arg2index = {}
        self.request._fixture_defs = {}
        self.request._arg2fixturedefs = self.test._fixtureinfo.name2fixturedefs.copy()

    def getfixturevalue(self, fixture):
        if not self.can_be_used:
            raise ValueError("Can't get fixture value. Other test is active.")
        return self.request.getfixturevalue(fixture)

    def setfixture(self, fixture, value):
        if not self.can_be_used:
            raise ValueError("Can't set fixture value. Other test is active.")
        if fixture in self.request._fixture_defs:
            raise ValueError("Fixture is already set.")
        add_fixture_to_test(fixture, value, self.request)

    def setfixturevalue(self, fixture, value):
        if not self.can_be_used:
            raise ValueError("Can't set fixture value. Other test is active.")
        if fixture in self.request._fixture_defs:
            raise ValueError("Fixture is already set.")
        fixturedef = self.request._getnextfixturedef(fixture)
        try:
            param = self.request._pyfuncitem.callspec.getparam(fixture)
        except (AttributeError, ValueError):
            param = 0
        fixturedef.cached_result = (value, param, None)
        self.request._fixture_defs[fixture] = fixturedef

        def finish():
            fixturedef.cached_result = None

        self.session._setupstate.addfinalizer(finish, self.test)

    def get_current_fixture_values(self):
        fixture_values = {}
        for f in self.fixtures:
            fdef = self.request._fixture_defs.get(f)
            if fdef:
                fixture_values[f] = fdef.cached_result[0]
            else:
                fixture_values[f] = None

        return fixture_values

    def print_fixture_code(self, fixture=None):
        if fixture:
            fixtures = [fixture]
        else:
            fixtures = self.fixtures

        for f in fixtures:
            fixturedefs = self.test._fixtureinfo.name2fixturedefs.get(f)
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
        active = self.pytestsession.current_test == self
        return f"<PytestTest {self.test.name}{' (active)' if active else ''}>"

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
    request._arg2fixturedefs[fixture_name] = (*request._arg2fixturedefs[fixture_name][:-1], fixture_def)


def get_session(args=None, plugins=None):
    if isinstance(args, str):
        args = args.split()
    args = args or []
    args.append('-s')

    # config.main
    conf = config._prepareconfig(args, plugins)

    # main.wrap_session
    session = main.Session.from_config(config=conf)

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


def cleanup_config(config, session):
    try:
        session._setupstate.teardown_all()
    except Exception as exc:
        sys.stderr.write('{}: {}\n'.format(type(exc).__name__, exc))
    try:
        config.hook.pytest_sessionfinish(session=session, existatus=session.exitstatus)
    except Exception as exc:
        sys.stderr.write('{}: {}\n'.format(type(exc).__name__, exc))
    config._ensure_unconfigure()


