# -*- coding: utf-8 -*-
from __future__ import print_function, absolute_import
__all__ = [
    'DOWN',
    'UP',
    'DATA_ENCODER',
    'DATA_DECODER',
    'DATA_ROOT',
    'DATA_FILE',
    'get_entry',
    'InvalidTag',
    'is_match',
    'one',
    'read',
    'search',
    'tag',
    'untag',
    'validate_tag',
    'write',
    'make_tag_path',
]
import os
import json
import string
import threading
import yaml
from functools import partial
from scandir import walk
from fsfs import util

# 2 to 3 compat
try:
    basestring
except NameError:
    basestring = str, bytes


DOWN = 0
UP = 1
DATA_ENCODER = partial(yaml.safe_dump, default_flow_style=False)
DATA_DECODER = yaml.load
DATA_ROOT = '.data'
DATA_FILE = 'data'
_LOCAL = threading.local()


def get_cache():
    '''Get thread local cache.'''

    if not hasattr(_LOCAL, 'cache'):
        _LOCAL.cache = {}
    return _LOCAL.cache


class InvalidTag(Exception):
    pass


def validate_tag(tag):
    '''Keys can only contain letters, numbers and these characters: .-_'''

    valid_chars = '.-_' + string.ascii_letters + string.digits
    if not all([c in valid_chars for c in tag]):
        raise InvalidTag(
            'Not a valid tag: {}\n'.format(tag) +
            'Keys can only contain letters, numbers and .-_'
        )
    return True


def make_tag_path(root, tag):
    '''Tag name to tag filepath

    Arguments:
        root (str): Directory
        tag (str): tag str

    Returns:
        str: {root}/{DATA_ROOT}/tag_{tag}
    '''

    return util.unipath(root, DATA_ROOT, 'tag_' + tag)


def get_entry(root):
    '''Get entry from cache

    Arguments:
        root (str): Directory

    Returns:
        :class:`models.Entry`: retrieved from cache
    '''

    cache = get_cache()
    if root in cache:
        return cache[root]

    from fsfs import models
    return cache.setdefault(root, models.Entry(root))


def clear_cache():
    '''Clear entry cache'''

    get_cache().clear()


def read(root, *keys):
    '''Read metadata from directory

    Arguments:
        root (str): Directory containing metadata
        *keys (List[str]): list of keys to retrieve. If no keys are passed
            return all key, value pairs.

    Returns:
        dict: key, value pairs stored at root
    '''

    entry = get_entry(root)
    return entry.read(*keys)


def write(root, **data):
    '''Write metadata to directory

    Arguments:
        root (str): Directory to write to
        **data (dict): key, value pairs to write

    Returns:
        None
    '''

    entry = get_entry(root)
    entry.write(**data)


def delete(root, remove_root=False):
    '''Delete a directory's metadata and tags.

    Arguments:
        root (str): Directory to remove metadata and tags from
        remove_root (bool): Delete the directory as well. Defaults to False.

    Returns:
        None
    '''

    entry = get_entry(root)
    entry.delete(root, remove_root)


def tag(root, *tags):
    '''Tag a directory as an Entry with the provided tags.

    Arguments:
        root (str): Directory to tag
        *tags (List[str]): Tags to add to directory like: 'asset' or 'project'
    '''

    for tag in tags:
        tag_path = make_tag_path(root, tag)
        util.touch(tag_path)


def untag(root, *tags):
    '''Remove a tag from a directory.

    Arguments:
        root (str): Directory to remove tags from
        *tags (List[str]): Tags to remove like: 'asset' or 'project'
    '''

    for tag in tags:
        tag_path = make_tag_path(root, tag)
        if os.path.isfile(tag_path):
            os.remove(tag_path)


def search(root, tags=None, direction=DOWN, depth=0, skip_root=False):
    '''Search a root directory yielding Entry objects that match tags. A tag
    is a string containing letters, numbers or any of these characters: .-_

    You can specify a direction to search (fsfs.UP or fsfs.DOWN) and a maximum
    search depth. If no tag arguments are passed search yields all Entries.

    Arguments:
        root (str): Directory to search
        *tags (str): Tags to match
        direction (int): Direction to search (fsfs.UP or fsfs.DOWN)

    Returns:
        generator: yielding :class:`models.Entry` matches
    '''

    tags = util.tupilize(tags)
    [validate_tag(tag) for tag in tags]

    if direction == DOWN:

        level = 0
        for root, _, _ in walk(root):

            level += 1
            if depth and level > depth:
                break

            if skip_root and level == 1:
                continue

            if is_match(root, *tags):
                yield get_entry(util.unipath(root))

    if direction == UP:

        level = 0
        next_root = util.unipath(root)
        while True:

            root = next_root

            level += 1
            if depth and level > depth:
                break

            if skip_root and level == 1:
                next_root = os.path.dirname(root)
                continue

            if is_match(root, *tags):
                yield get_entry(root)

            next_root = os.path.dirname(root)
            if next_root == root:
                break


def one(*args, **kwargs):
    '''Return first result from search.

    See also:
        :func:`fsfs.api.search`

    Returns:
        :class:`fsfs.models.Entry`
    '''

    matches = search(*args, **kwargs)
    try:
        return matches.next()
    except StopIteration:  # no result
        return


def is_match(root, *tags):
    '''
    Return True if the root directory matches all of the tags provided. If no
    tags are provided check if the DATA_ROOT directory exists.

    Arguments:
        root (str): Directory to check
        tags (List[str]): Tags to check

    Returns:
        bool
    '''

    if not tags:
        return os.path.isdir(util.unipath(root, DATA_ROOT))

    match = True
    for tag in tags:
        tag_path = make_tag_path(root, tag)
        if not os.path.isfile(tag_path):
            match = False

    return match
