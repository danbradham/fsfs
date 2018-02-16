# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
import os
import inspect
from functools import wraps
from scandir import walk, scandir
from fsfs import util, api
try:
    import itertools
    izip = itertools.izip
except NameError:
    izip = zip


DOWN = 0
UP = 1


class search(object):

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

    def __iter__(self):

        if self.selector:
            entries = _select_from_tree(
                self.root,
                self.selector,
                self.sep,
                self.direction,
                self.depth,
                self.skip_root
            )
        else:
            entries = _search(
                self.root,
                self.direction,
                self.depth,
                self.skip_root
            )

        if not self.predicates:
            return entries
        else:
            return (
                e for e in entries
                if all([p(e) for p in self.predicates])
            )

    def one(self):
        try:
            return self.__iter__().next()
        except StopIteration:
            return None

    def tags(self, *tags):
        [api.validate_tag(tag) for tag in tags]
        return search(
            self.root,
            self.direction,
            self.depth,
            self.skip_root,
            self.predicates + [lambda e: all([tag in e.tags for tag in tags])]
        )

    def uuid(self, uuid):
        return search(
            self.root,
            self.direction,
            self.depth,
            self.skip_root,
            self.predicates + [lambda e: uuid == e.uuid]
        )

    def name(self, name):
        return search(
            self.root,
            self.direction,
            self.depth,
            self.skip_root,
            self.predicates + [lambda e: name in e.name]
        )

    def select(self, selector, sep='/'):
        return search(
            self.root,
            self.direction,
            self.depth,
            self.skip_root,
            self.predicates,
            selector,
            sep
        )

    def filter(self, predicate):
        return search(
            self.root,
            self.direction,
            self.depth,
            self.skip_root,
            self.predicates + [predicate]
        )


def _search(root, direction=DOWN, depth=10, skip_root=False):
    '''Search a root directory yielding Entry objects that match tags. A tag
    is a string containing letters, numbers or any of these characters: .-_

    You can specify a direction to search (fsfs.UP or fsfs.DOWN) and a maximum
    search depth. If no tag arguments are passed search yields all Entries.

    Arguments:
        root (str): Directory to search
        *tags (str): Tags to match
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


def regenerator(generator_fn):
    '''A decorator for generators. When a generator is yielded, it's
    items are yielded one by one. This allows generators to be recursive
    without requiring the yield from syntax of Python 3.3+.

    Examples:

        >>> @regenerator
        ... def count_down(number):
        ...     for i in range(number):
        ...         yield i
        ...     yield count_down(number - 1)
        >>> list(count_down(3))
        [2, 1, 0, 1, 0, 0]
    '''

    @wraps(generator_fn)
    def flatten_generator(*args, **kwargs):
        stack = [generator_fn(*args, **kwargs)]
        while True:
            try:
                item = stack[-1].next()
            except StopIteration:
                stack.pop()
                if not stack:
                    raise
            else:
                if inspect.isgenerator(item):
                    stack.append(item)
                else:
                    yield item
    return flatten_generator



@regenerator
def _searchtree_dn(root, depth=10, skip_root=False, level=0, visited=None):
    '''Search tree yielding full path to entries'''

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
                yield _searchtree_dn(
                    root + '/' + entry.name,
                    depth,
                    skip_root,
                    level + 1,
                    list(visited)
                )


def _searchtree_up(root, depth=10, skip_root=False):

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


def _searchtree(root, direction=DOWN, depth=10, skip_root=False):
    if direction == DOWN:
        return _searchtree_dn(root, depth, skip_root)
    elif direction == UP:
        return _searchtree_up(root, depth, skip_root)
    else:
        raise RuntimeError('Invalid direction: ' + str(direction))


def _select_from_tree(root, selector, sep='/', direction=DOWN,
                      depth=10, skip_root=False):
    parts = selector.split(sep)
    num_parts = len(parts)

    for branch in _searchtree(root, direction, depth, skip_root):
        num_branch_parts = len(branch)

        if num_parts > num_branch_parts:
            continue

        elif num_parts == num_branch_parts:

            for part, entry in izip(parts, branch):
                if part not in entry.name:
                    break
            else:
                yield entry

        else: # Fuzzy match

            entry = None
            b_i = 0
            for part in parts:
                for i, entry in enumerate(branch[b_i:]):
                    if part in entry.name:
                        b_i += i + 1
                        break
                else:
                    break
            else:
                if entry is branch[-1]:
                    yield entry
