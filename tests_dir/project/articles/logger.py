LOGGER = []


def log_setup(fn, *args):
    args = map(str, args)
    if callable(fn):
        LOGGER.append(f'SETUP: {fn.__module__}.{fn.__name__} {",".join(args)}')
    else:
        LOGGER.append(f'SETUP: {fn} {",".join(args)}' )
    print(LOGGER[-1])


def log_teardown(fn, *args):
    args = map(str, args)
    if callable(fn):
        LOGGER.append(f'TEARDOWN: {fn.__module__}.{fn.__name__} {",".join(args)}')
    else:
        LOGGER.append(f'TEARDOWN: {fn} {",".join(args)}')
    print(LOGGER[-1])


