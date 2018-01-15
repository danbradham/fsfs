# -*- coding: utf-8 -*-
__all__ = ['touch', 'unipath', 'tupilize', 'update_dict']
import os
import errno
import collections


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
    '''os.path.join with forward slashes only.'''

    return os.path.join(*paths).replace('\\', '/')


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
        raise ValueError('Can not tupilize: ', obj)


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
