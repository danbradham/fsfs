# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__all__ = ['File']


class File(object):
    '''A thin wrapper around the standard python file object. Allows users to
    setup a file-like object without actually opening it.

    Examples:
        >>> import doctest
        >>> with open('tmpfile', 'w') as f:
        ...     _ = f.write('hello') # doctest: +ELLIPSIS

        open, read, and close a File.

        >>> f = File('tmpfile', 'r')
        >>> f.open()  # doctest: +ELLIPSIS
        <fsfs.types.File object at ...>
        >>> assert f.opened
        >>> f.read()
        'hello'
        >>> f.close()
        >>> assert f.closed

        use File as a context manager.

        >>> f = File('tmpfile', 'r')
        >>> with f.open():
        ...     f.read()
        'hello'
        >>> assert f.closed

        >>> import os; os.remove('tmpfile')
    '''

    def __init__(self, name, mode):
        self.name = name
        self.mode = mode
        self._file = None

    def __getattr__(self, attr):
        if self._file:
            return getattr(self._file, attr)
        file_attrs = [x for x in dir(file) if not x.startswith('__')]
        if attr in file_attrs:
            msg = "'{}' not available until 'File.open' is called".format(attr)
        else:
            msg = "'File' object has no attribute '{}'".format(attr)
        raise AttributeError(msg)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        '''Forward exit to underlying file object'''

        return self._file.__exit__(exc_type, exc_val, exc_tb)

    @property
    def opened(self):
        '''Check if File is opened'''

        if not self._file:
            return False
        return not self._file.closed

    @property
    def closed(self):
        '''Check if File is closed'''

        if not self._file:
            return False
        return self._file.closed

    def open(self):
        '''Open acts like the builtin open function, it works as a regular
        function and as a context manager. The name and mode passed to the File
        constructor are used as the arguments for the builtin open. The
        resulting file object is stored in the :attr:`File._file`
        '''

        self._file = open(self.name, self.mode)
        return self
