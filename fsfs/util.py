# -*- coding: utf-8 -*-
__all__ = [
    'touch',
    'unipath',
    'tupilize',
    'update_dict',
    'copy_file',
    'suppress'
]
import os
import errno
import collections
from _compat import basestring


BINARY = os.__dict__.get('O_BINARY', 0)  # Windows has a binary flag
RFLAGS = os.O_RDONLY | BINARY
WFLAGS = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | BINARY
GIGABYTES = 1024 ** 3
MEGABYTES = 1024 ** 2
KILOBYTES = 1024
BYTES = 1
DEFAULT_BUFFER = 256 * KILOBYTES
MINIMUM_BUFFER = 1 * KILOBYTES


def optimize_buffer(f, buffer_size):
    '''Calculate optimate buffer size for smaller files'''

    return max(min(buffer_size, os.path.getsize(f)), MINIMUM_BUFFER)


def suppress(fn, *args, **kwargs):
    '''Never use this...ehhhhh, maybe use it. Suppresses all exceptions raised
    by a callable.

    Arguments:
        fn (callable): function to call
        *args: args to pass to fn
        **kwargs: kwargs to pass to fn

    Returns:
        function return value or None

    Raises:
        Nothing...ever
    '''

    try:
        return fn(*args, **kwargs)
    except:
        pass


def copy_file(src, dest, buffer_size=DEFAULT_BUFFER):
    '''Copy operations can be optimized by setting the buffer size for read
    operations and that's just what copy_file does. copy_file has a default
    buffer size of 256 KB, which increases the speed of file copying in most
    cases. For smaller files the buffer size is reduced to the file size or a minimum of MINIMUM_BUFFER (1 KB).

    See also:
        http://blogs.blumetech.com/blumetechs-tech-blog/2011/05/faster-python-file-copy.html
        https://stackoverflow.com/questions/22078621/python-how-to-copy-files-fast/28129677#28129677

    Arguments:
        src (str):
    '''

    if shutil._samefile(src, dest):
        raise OSError('Source and destination can not be the same...')

    destdir = os.path.dirname(dest)
    if not os.path.exists(destdir):
        os.makedirs(destdir)

    buffer_size = optimize_buffer(src, buffer_size)
    try:
        i_file = os.open(src, RFLAGS)
        i_stat = os.fstat(i_file)
        o_file = os.open(dest, WFLAGS, i_stat.st_mode)

        while True:
            b = os.read(i_file, buffer_size)
            if b == '':
                break
            os.write(o_file, b)
    finally:
        suppress(os.close, i_file)
        suppress(os.close, o_file)


def touch(file):
    '''Create an empty file or update the date modified of an existing file'''

    root = os.path.dirname(file)
    try:
        os.makedirs(root)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    with open(file, 'a'):
        os.utime(file, None)


def unipath(*paths):
    '''Like os.path.join but returns an absolute path with forward slashes.'''

    return os.path.abspath(os.path.join(*paths)).replace('\\', '/')


def tupilize(obj):
    '''Coerce obj to tuple'''

    if isinstance(obj, tuple):
        return obj
    elif obj is None:
        return tuple()
    elif isinstance(obj, basestring):
        return (obj,)
    elif isinstance(obj, list):
        return tuple(obj)
    else:
        raise ValueError("Can't tupilize: ", obj)


def update_dict(d, u):
    '''Update a dict recursively.

    See also:
        https://stackoverflow.com/questions/3232943/update-value-of-a-nested-dictionary-of-varying-depth
    '''

    for k, v in u.items():
        if isinstance(v, collections.Mapping):
            dv = d.get(k, {})
            if isinstance(dv, collections.Mapping):
                d[k] = update_dict(dv, v)
            else:
                d[k] = v
        else:
            d[k] = v
    return d
