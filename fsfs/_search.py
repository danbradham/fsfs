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
import inspect
from functools import wraps
from scandir import walk, scandir
from fsfs import util, api
from fsfs._compat import izip


DOWN = 0
UP = 1


class Search(object):

    def __init__(
        self,
        root,
        direction=DOWN,
        depth=10,
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

    def send(self, value):
        return self._generator.send(value)

    def next(self):
        return self._generator.send(None)

    def throw(self, typ, val=None, tb=None):
        self._generator.throw(typ, val, tb)

    def close(self):
        self._generator.close()

    def one(self):
        try:
            return self.next()
        except StopIteration:
            return None

    def clone(self, **overrides):
        kwargs = dict(
            root=self.root,
            direction=self.direction,
            depth=self.depth,
            skip_root=self.skip_root,
            predicates=self.predicates,
            selector=self.selector,
            sep=self.sep
        )
        kwargs.update(**overrides)
        return Search(**kwargs)

    def tags(self, *tags):
        [api.validate_tag(tag) for tag in tags]
        predicate = lambda e: all([tag in e.tags for tag in tags])
        return self.clone(predicates=self.predicates + [predicate])

    def uuid(self, uuid):
        predicate = lambda e: uuid == e.uuid
        return self.clone(predicates=self.predicates + [predicate])

    def name(self, name, sep='/'):

        if sep in name:
            name = name.strip(sep)
            return self.clone(selector=name, sep=sep)

        predicate = lambda e: name in e.name
        return self.clone(predicates=self.predicates + [predicate])

    def filter(self, predicate):
        return self.clone(predicates=self.predicates + [predicate])


def search(root, direction=DOWN, depth=10, skip_root=False):
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

    if direction == DOWN:

        base_level = root.count(os.sep)
        for root, subdirs, _ in walk(root):

            level = root.count(os.sep) - base_level

            if depth and level == depth:
                del subdirs[:]

            subdirs[:] = [
                d for d in subdirs if not d == api.get_data_root()
            ]

            if skip_root and level == 0:
                continue

            if os.path.isdir(root + '/' + api.get_data_root()):
                yield api.get_entry(util.unipath(root))

    elif direction == UP:

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

            if os.path.isdir(root + '/' + api.get_data_root()):
                yield api.get_entry(root)

            next_root = os.path.dirname(root)
            if next_root == root:
                break

    else:

        raise RuntimeError('Invalid direction: ' + str(direction))


@util.regenerator
def _search_tree_dn(root, depth=10, skip_root=False, level=0, visited=None):

    if visited is None:
        visited = []
        root = util.unipath(root)

    if level == depth:
        if visited:
            yield visited
        raise StopIteration

    entries = scandir(root)
    only_data = True

    while True:
        try:
            entry = next(entries)
        except StopIteration:
            break

        if entry.is_dir():
            if entry.name == api.get_data_root():
                if skip_root and level == 0:
                    pass
                else:
                    visited.append(api.get_entry(root))
                    yield visited
            else:
                only_data = False
                yield _search_tree_dn(
                    root + '/' + entry.name,
                    depth,
                    skip_root,
                    level + 1,
                    list(visited)
                )


def _search_tree_up(root, depth=10, skip_root=False):

    visited = []

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

        if os.path.isdir(root + '/' + api.get_data_root()):
            visited.append(api.get_entry(root))
            yield visited[::-1]

        next_root = os.path.dirname(root)
        if next_root == root:
            break


def search_tree(root, direction=DOWN, depth=10, skip_root=False):
    '''Walks up or down a tree yielding lists containing all Entries '''

    if direction == DOWN:
        return _search_tree_dn(root, depth, skip_root)
    elif direction == UP:
        return _search_tree_up(root, depth, skip_root)
    else:
        raise RuntimeError('Invalid direction: ' + str(direction))


def select_from_tree(root, selector, sep='/', direction=DOWN,
                      depth=10, skip_root=False):
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
                        break # Match Found
                else:
                    break # Match Not Found
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
        return matches.next()
    except StopIteration:  # no result
        return

