"""Process-local admission control; not a recommendation/result cache."""
from contextlib import contextmanager
from threading import Lock

_lock=Lock()
_active=set()


@contextmanager
def single_request(key):
    with _lock:
        if key in _active:
            raise RuntimeError('Another request is already running for this VM')
        _active.add(key)
    try:
        yield
    finally:
        with _lock:_active.discard(key)
