# -*- coding: utf-8 -*-
'''
Low-level Search API
'''
from __future__ import absolute_import, division, print_function

__all__ = [
    'DOWN',
    'UP',
    'Search',
    'search',
    'search_tree',
    'search_uuid',
    'one_uuid',
    'select_from_tree',
]

import os
from scandir import walk, scandir
import errno
from fsfs import util, api
from fsfs._compat import izip
from fsfs.constants import (
    DOWN,
    UP,
    DEFAULT_SEARCH_DN_DEPTH,
    DEFAULT_SEARCH_UP_DEPTH
)

IGNORE = (
    errno.EACCES,
    errno.ENOENT,
    errno.EIO,
    errno.EPERM,
    59,  # WinError network access
)


class Search(object):

    def __init__(
        self,
        root,
        direction=DOWN,
        depth=None,
        skip_root=False,
        predicates=None,
        selector=None,
        sep=None
    ):

        self.root = root
        self.direction = direction
        self.depth = depth
        self.skip_root = skip_root
        self.predicates = predicates or []
        self.selector = selector
        self.sep = sep
        self._generator = self._make_generator()

    def _make_generator(self):
        if self.selector:
            entries = select_from_tree(
                self.root,
                self.selector,
                self.sep,
                self.direction,
                self.depth,
                self.skip_root
            )
        else:
            entries = search(
                self.root,
                self.direction,
                self.depth,
                self.skip_root
            )

        if not self.predicates:
            return entries
        elif len(self.predicates) == 1:
            p = self.predicates[0]
            return (e for e in entries if p(e))
        else:
            return (e for e in entries if all([p(e) for p in self.predicates]))

    def __iter__(self):
        return self

    def __next__(self):
        return self._generator.send(None)

    next = __next__

    def send(self, value):
        return self._generator.send(value)

    def throw(self, typ, val=None, tb=None):
        self._generator.throw(typ, val, tb)

    def close(self):
        self._generator.close()

    def one(self):
        '''Returns the first object yielded'''

        try:
            return self.next()
        except StopIteration:
            return None

    def clone(self, **kwargs):
        '''Clone this Search object. Pass kwargs to override attributes on
        the Search object.'''

        kwargs.setdefault('root', self.root)
        kwargs.setdefault('direction', self.direction)
        kwargs.setdefault('depth', self.depth)
        kwargs.setdefault('skip_root', self.skip_root)
        kwargs.setdefault('predicates', self.predicates)
        kwargs.setdefault('selector', self.selector)
        kwargs.setdefault('sep', self.sep)
        return Search(**kwargs)

    def tags(self, *tags):
        '''Retruns a new Search object yielding entities that match tags'''

        for tag in tags:
            api.validate_tag(tag)

        predicate = lambda e: all([tag in e.tags for tag in tags])
        return self.clone(predicates=self.predicates + [predicate])

    def uuid(self, uuid):
        '''Returns a new Search object yielding entities that match uuid'''

        predicate = lambda e: uuid == e.uuid
        return self.clone(predicates=self.predicates + [predicate])

    def name(self, name, sep='/'):
        '''Returns a new Search object yielding objects that match name'''

        if sep in name:
            name = name.strip(sep)
            return self.clone(selector=name, sep=sep)

        predicate = lambda e: name in e.name
        return self.clone(predicates=self.predicates + [predicate])

    def filter(self, predicate):
        '''Returns a new Search object with a new filter predicate.

        A predicate is a function that accepts an entity and returns True or
        False'''

        return self.clone(predicates=self.predicates + [predicate])


def safe_scandir(root):
    '''Silences permissions errors raised by scandir generator'''

    try:
        gen = scandir(root)
    except OSError as e:
        if e.errno not in IGNORE:
            raise
        return

    while True:
        try:
            yield gen.next()
        except OSError as e:
            if e.errno not in IGNORE:
                raise


@util.regenerator
def _search_dn(root, depth=DEFAULT_SEARCH_DN_DEPTH, skip_root=False,
               level=0, at_root=True):

    if os.path.isdir(root + '/' + api.get_data_root()):
        level = 0
        if skip_root and at_root:
            pass
        else:
            yield api.get_entry(util.unipath(root))

    if level == depth:
        raise StopIteration

    for dir_entry in safe_scandir(root):

        if dir_entry.is_dir() and dir_entry.name != api.get_data_root():
            yield _search_dn(
                dir_entry.path,
                depth,
                skip_root,
                level + 1,
                False
            )


def _search_up(root, depth=DEFAULT_SEARCH_UP_DEPTH, skip_root=False):

    level = -1
    next_root = root
    while True:

        root = next_root
        level += 1

        if depth and level > depth:
            break

        if skip_root and level == 0:
            next_root = os.path.dirname(root)
            continue

        if os.path.isdir(root + '/' + api.get_data_root()):
            yield api.get_entry(root)

        next_root = os.path.dirname(root)
        if next_root == root:
            break


def search(root, direction=DOWN, depth=None, skip_root=False):
    '''Search a root directory yielding Entry objects. You can specify a
    direction to search (fsfs.UP or fsfs.DOWN) and a maximum search depth.

    Arguments:
        root (str): Directory to search
        direction (int): Direction to search (fsfs.UP or fsfs.DOWN)
        depth (int): Maximum depth of search
        skip_root (bool): Skip search in root directory

    Returns:
        generator: yielding :class:`models.Entry` matches
    '''

    root = util.unipath(root)
    if direction == DOWN:
        depth = depth or DEFAULT_SEARCH_DN_DEPTH
        return _search_dn(root, depth, skip_root)
    elif direction == UP:
        depth = depth or DEFAULT_SEARCH_UP_DEPTH
        return _search_up(root, depth, skip_root)
    else:
        raise RuntimeError('Invalid direction: ' + str(direction))


@util.regenerator
def _search_tree_dn(root, depth=DEFAULT_SEARCH_DN_DEPTH, skip_root=False,
                    level=0, at_root=True, visited=None):

    if visited is None:
        visited = []

    if os.path.isdir(root + '/' + api.get_data_root()):
        level = 0
        visited.append(api.get_entry(util.unipath(root)))
        yield visited

    if level == depth:
        raise StopIteration

    for dir_entry in safe_scandir(root):

        if dir_entry.is_dir() and dir_entry.name != api.get_data_root():
            yield _search_tree_dn(
                dir_entry.path,
                depth,
                skip_root,
                level + 1,
                False,
                list(visited)
            )


def _search_tree_up(root, depth=DEFAULT_SEARCH_UP_DEPTH, skip_root=False):

    visited = []

    level = -1
    next_root = root
    while True:

        root = next_root
        level += 1

        if depth and level > depth:
            break

        if skip_root and level == 0:
            next_root = os.path.dirname(root)
            continue

        if os.path.isdir(root + '/' + api.get_data_root()):
            visited.append(api.get_entry(root))
            yield visited[::-1]

        next_root = os.path.dirname(root)
        if next_root == root:
            break


def search_tree(root, direction=DOWN, depth=None, skip_root=False):
    '''Walks up or down a tree yielding lists containing all Entries '''

    if direction == DOWN:
        depth = depth or DEFAULT_SEARCH_DN_DEPTH
        return _search_tree_dn(util.unipath(root), depth, skip_root)
    elif direction == UP:
        depth = depth or DEFAULT_SEARCH_UP_DEPTH
        return _search_tree_up(util.unipath(root), depth, skip_root)
    else:
        raise RuntimeError('Invalid direction: ' + str(direction))


def select_from_tree(root, selector, sep='/', direction=DOWN,
                     depth=None, skip_root=False):
    '''This method is used under the hood by the Search class, you shouldn't
    need to call it manually.

    Walk tree up or down yielding entries that match the selector.
    A selector is a string representing a hierarchy of names. The selector
    `my_parent/my_entry` would match an Entry named `my_entry` within an Entry
    named `my_parent`. You can use a custom separator by passing the
    keyword argument `sep`.

    Arguments:
        root (str): Directory to search
        selector (str): Hierarchy of names separated by sep
        sep (str): Separator used to split selector
        direction (int): Direction to search (fsfs.UP or fsfs.DOWN)
        depth (int): Maximum depth of search
        skip_root (bool): Skip search in root directory

    Returns:
        generator: yielding :class:`models.Entry` matches
    '''
    parts = selector.split(sep)
    num_parts = len(parts)

    for branch in search_tree(root, direction, depth, skip_root):
        num_branch_parts = len(branch)

        if num_parts > num_branch_parts:
            continue

        elif num_parts == num_branch_parts:

            for part, entry in izip(parts, branch):
                if part not in entry.name:
                    break
            else:
                yield entry

        else:
            # num_parts < num_branch_parts
            # Make sure all select parts are in the branch and
            # make sure the last part matches the last elem in branch

            entry = None
            b_i = 0
            for part in parts:
                for i, entry in enumerate(branch[b_i:]):
                    if part in entry.name:
                        b_i += i + 1
                        break  # Match Found
                else:
                    break  # Match Not Found
            else:
                # We made it through the for loop without encountering a break
                # All parts were found
                if entry is branch[-1]:
                    yield entry


def search_uuid(root, uuid, direction=DOWN, depth=0, skip_root=False):
    '''Like search but finds a uuid file. This is a low-level function used
    to lookup missing entries.

    Arguments:
        root (str): Directory to search
        uuid (str): UUID to match
        direction (int): Direction to search (fsfs.UP or fsfs.DOWN)
        depth (int): Maximum depth of search
        skip_root (bool): Skip search in root directory

    Returns:
        generator yielding (root, data_root, uuid_file)
    '''

    if direction == DOWN:

        base_level = root.count(os.sep)
        for root, subdirs, _ in walk(root):

            level = root.count(os.sep) - base_level

            if depth and level == depth:
                del subdirs[:]

            subdirs[:] = [d for d in subdirs if not d == api.get_data_root()]

            if skip_root and level == 0:
                continue

            root = util.unipath(root)
            data_root = root + '/' + api.get_data_root()
            uuid_file = root + '/' + api.get_data_root() + '/' + 'uuid_' + uuid
            if os.path.isfile(uuid_file):
                yield root, data_root, uuid_file

    if direction == UP:

        level = -1
        next_root = util.unipath(root)
        while True:

            root = next_root
            level += 1

            if depth and level > depth:
                break

            if skip_root and level == 0:
                next_root = os.path.dirname(root)
                continue

            data_root = root + '/' + api.get_data_root()
            uuid_path = root + '/' + api.get_data_root() + 'uuid_' + uuid
            if os.path.isfile(uuid_path):
                yield root, data_root, uuid_file

            next_root = os.path.dirname(root)
            if next_root == root:
                break


def one_uuid(*args, **kwargs):
    '''Return first result from search_uuid.

    Returns:
        tuple: (root, data_root, uuid_file)
    '''

    matches = search_uuid(*args, **kwargs)
    try:
        return next(matches)
    except StopIteration:
        return
