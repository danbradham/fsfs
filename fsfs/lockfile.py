# -*- coding: utf-8 -*-
from __future__ import absolute_import

__all__ = [
    'LockFileError',
    'LockFileTimeOutError',
    'LockFilePump',
    'LockFile',
    'lockfile'
]

import atexit
import os
import time
import errno
import threading
from warnings import warn
from datetime import datetime
from timeit import default_timer
from contextlib import contextmanager


class LockFileError(Exception): pass
class LockFileTimeOutError(Exception): pass


class LockFilePump(threading.Thread):
    '''A daemon thread that updates all acquired LockFiles held by this
    process. This keeps the locks from expiring while the process has them.
    '''

    def __init__(self):
        super(LockFilePump, self).__init__()
        self.daemon = True
        self._shutdown = threading.Event()
        self._stopped = threading.Event()
        self._started = threading.Event()
        atexit.register(self.stop)

    @property
    def started(self):
        return self._started.is_set()

    @property
    def stopped(self):
        return self._stopped.is_set()

    @property
    def shutdown(self):
        return self._shutdown.is_set()

    def stop(self):
        if not self.started and not self.shutdown:
            return

        self._shutdown.set()
        self._stopped.wait()
        if self.isAlive():
            self.join()

    def run(self):

        try:
            self._started.set()

            while True:

                for lock in list(LockFile._acquired_locks):
                    if lock.locked:
                        try:
                            lock._touch()
                        except OSError as e:
                            msg = (
                                'PumpThread failed to update mtime of lock: \n'
                                '{errno}: {massge}'
                            ).format(e.errno, e.message)
                            warn(msg)

                if self._shutdown.wait(LockFile._pump_interval_):
                    break

        finally:
            self._stopped.set()


class LockFile(object):
    '''Uses a file as a lock. When a LockFile is acquired a file is created at
    its associated path. While this file exists no other process can acquire
    the lock. When a LockFile is released, the file is removed, allowing other
    processes to acquire the lock.

    To make sure we don't leave hanging locks, locks expire after
    LockFile._expiration (defaults to 2 seconds). This works because we
    have a background thread constantly updating the mtime of all locks the
    current process holds. Once this process exits, any hanging locks will
    finally have a static mtime, and they can expire.

    Examples:

        Acquire a lock.

            >>> lock = LockFile('.lock')
            >>> lock.acquire()
            >>> assert lock.acquired
            >>> assert lock.locked

        Acquire a lock using a timeout.

            >>> lock2 = LockFile('.lock')
            >>> assert not lock2.acquired
            >>> assert lock2.locked
            >>> lock2.acquire(0.1)  # doctest: +IGNORE_EXCEPTION_DETAIL
            Traceback (most recent call last):
            ...
            LockFileTimeOutError: Timed out while trying to acquire lock...

        Release a lock and acquire a new one using another LockFile instance.

            >>> lock.release()
            >>> assert not lock.acquired
            >>> lock2.acquire()
            >>> assert lock2.acquired
            >>> lock2.release()
            >>> assert not lock2.acquired

        Use LockFile as a contextmanager.

            >>> with lock:
            ...     assert lock.acquired
            ...

        Call a LockFile to use it as a contextmanager with a timeout.

            >>> lock2.acquire()
            >>> with lock(0.1):
            ...     pass  # doctest: +IGNORE_EXCEPTION_DETAIL
            Traceback (most recent call last):
            ...
            LockFileTimeOutError: Timed out while trying to acquire lock...
            >>> lock2.release()
    '''

    _pump_ = LockFilePump()
    _pump_interval_ = 1
    _expiration = 2  # Expiration must be greater than pump interval
    _acquired_locks = []

    def __init__(self, path):

        self.path = os.path.abspath(path)
        self.acquired = False
        self._depth = 0
        self._start_pump()

    def __enter__(self):
        if self._depth == 0:
            self.acquire()
        self._depth += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._depth == 1:
            self.release()
        self._depth -= 1

    @contextmanager
    def __call__(self, timeout=0):

        try:
            if self._depth == 0:
                self.acquire(timeout)
            self._depth += 1
            yield self
        finally:
            if self._depth == 1:
                self.release()
            self._depth -= 1

    @property
    def locked(self):
        '''Check if this lock is currently locked...'''

        return os.path.exists(self.path)

    @property
    def expired(self):
        '''Check if this lock has expired...'''

        return self._time_since_modified() > self._expiration

    def _start_pump(self):
        '''Start the pump thread'''
        if self._pump_.started:
            return

        self._pump_.start()

        # Wait for pump thread to start
        while not self._pump_.started:
            time.sleep(0.01)

    def _touch(self):
        '''Touch the lock file, updates the files mtime'''

        with open(self.path, 'a'):
            os.utime(self.path, None)

    def _time_since_modified(self):
        '''Return the total seconds since the specified file was modified'''

        return (
            datetime.now() -
            datetime.fromtimestamp(os.path.getmtime(self.path))
        ).total_seconds()

    def _acquire_expired_lock(self):
        '''Attempt to acquire an expired lock'''

        self._release_lockfile()
        self._try_to_acquire()

        if not self.acquired:
            raise LockFileError('Failed to acquire expired lock...')

    def _try_to_acquire(self):
        '''Creates the lockfile on the filesystem. Returns True if the
        lockfile is successfully created.
        '''

        if self.acquired:
            self.acquired = True
            return

        if self.locked:
            self.acquired = False
            return

        self._touch()

        self._acquired_locks.append(self)
        self.acquired = True

    def acquire(self, timeout=0):
        '''Acquire the lock. Raises an exception when timeout is reached.

        Arguments:
            timeout (int or float): Amount of time to wait for lock
        '''

        self._try_to_acquire()
        if self.acquired:
            return

        if self.locked and self.expired:
            self._acquire_expired_lock()
            return

        s = default_timer()
        while not self.acquired:

            if timeout > 0 and default_timer() - s > timeout:
                raise LockFileTimeOutError(
                    'Timed out while trying to acquire lock...'
                )

            if self.locked and self.expired:
                self._acquire_expired_lock()
                return

            self._try_to_acquire()
            time.sleep(0.05)

    def _release_lockfile(self):
        '''Removes the lockfile on the filesystem. Returns True if the lockfile
        is successfully removed.
        '''

        try:
            os.remove(self.path)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise e
        finally:
            if self in self._acquired_locks:
                self._acquired_locks.remove(self)
            self.acquired = False

    def release(self):
        '''Release the lock'''

        if not self.acquired:
            raise LockFileError('Can not release an unacquired lock...')

        self._release_lockfile()

    @classmethod
    def _release_locks(cls):
        '''Releases all locks that are unreleased. This function is
        registered as an atexit function, making sure we do not leave any lock
        files floating around on program termination.
        '''

        for lock in list(cls._acquired_locks):
            lock.release()


@contextmanager
def lockfile(path, timeout=0):
    '''LockFile contextmanager, for when you only need to acquire a lock once.

    Arguments:
        path (str): path to the lockfile
        timeout (int or float): time to wait for the lock

    Returns:
        Acquired LockFile

    Raises:
        LockFileTimeOutError: when timeout reached

    Examples:

        >>> with lockfile('.lock') as l:
        ...     assert l.acquired

        >>> l = LockFile('.lock')
        >>> l.acquire()
        >>> with lockfile('.lock', 0.1):
        ...     pass  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
        ...
        LockFileTimeOutError: Timed out while trying to acquire lock...

    '''

    lock = LockFile(path)
    lock.acquire(timeout)

    try:
        yield lock
    finally:
        lock.release()


# Make sure that all locks are released on program exit
atexit.register(LockFile._release_locks)
