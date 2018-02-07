# -*- coding: utf-8 -*-
from __future__ import print_function, absolute_import

__all__ = [
    'DOWN',
    'UP',
    'get_policy',
    'set_policy',
    'set_default_policy',
    'get_data_decoder',
    'set_data_decoder',
    'decode_data',
    'get_data_encoder',
    'set_data_encoder',
    'encode_data',
    'get_data_root',
    'set_data_root',
    'get_data_file',
    'set_data_file',
    'get_entry_factory',
    'set_entry_factory',
    'get_entry',
    'InvalidTag',
    'validate_tag',
    'make_tag_path',
    'get_tags',
    'tag',
    'untag',
    'read',
    'write',
    'read_blob',
    'write_blob',
    'read_file',
    'write_file',
    'search_uuid',
    'one_uuid',
    'search',
    'one',
    'is_match',
]

import os
import json
import string
import errno
from scandir import walk, scandir
from fsfs import util


DOWN = 0
UP = 1


def get_policy():
    '''Get the global FsFsPolicy object

    See also:
        :class:`fsfs.policy.FsFsPolicy`
    '''
    from fsfs import policy
    return policy._global_policy


def set_policy(policy):
    '''Set the global FsFsPolicy object.

    See also:
        :class:`fsfs.policy.FsFsPolicy`
    '''
    from fsfs import policy
    policy._global_policy = policy


def set_default_policy():
    '''Set the global FsFsPolicy to it's default values.

    See also:
        :class:`fsfs.policy.DefaultPolicy`
    '''
    from fsfs import policy
    policy.DefaultPolicy.set_data_encoder(policy.DefaultEncoder)
    policy.DefaultPolicy.set_data_decoder(policy.DefaultDecoder)
    policy.DefaultPolicy.set_data_root(policy.DefaultRoot)
    policy.DefaultPolicy.set_data_file(policy.DefaultFile)
    policy.DefaultPolicy.set_entry_factory(policy.DefaultFactory)


def set_data_encoder(data_encoder):
    '''Set the global policy's data_encoder.

    Expects a callable like `json.dumps` or `yaml.dump`
    The default policy uses `yaml.safe_dump` with default_flow_style=False
    '''

    get_policy().set_data_encoder(data_encoder)


def get_data_encoder():
    '''Get the global policy's data_encoder'''

    return get_policy().get_data_encoder()


def set_data_decoder(data_decoder):
    '''Set the global policy's data_encoder.

    Expects a callable like `json.loads` or `yaml.load`
    The default policy uses `yaml.safe_load`
    '''


    get_policy().set_data_decoder(data_decoder)


def get_data_decoder():
    '''Get the global policy's data_decoder'''

    return get_policy().get_data_decoder()


def set_data_root(data_root):
    '''Set the global policy's data_root. The data_root is the name of the
    directory that stores metadata for an Entry

    The default policy's data_root is ".data"
    '''

    get_policy().set_data_root(data_root)


def get_data_root():
    '''Get the global policy's data_root'''

    return get_policy().get_data_root()


def set_data_file(data_file):
    '''Set the global policy's data_file. The data_file is the name of the
    file in the data_root that stores the actual encoded metadata for an Entry

    The default policy's data_root is ".data"
    '''

    get_policy().set_data_file(data_file)


def get_data_file():
    '''Get the global policy's data_file'''

    return get_policy().get_data_file()


def set_entry_factory(entry_factory):
    '''Set the global policy's entry_factory. The entry_factory is used to
    create Entry instances returned by `get_entry`, `search`, and `one`.

    The default entry_factory is :func:`fsfs.policy.default_entry_factory`.
    It stores Entry object's in a cache for quick lookup and generates the
    default implementation of Entry.

    Provide your own entry_factory to have fsfs yield your own Entry subclasses

    See also:
        :func:`fsfs.policy.default_entry_factory`
    '''

    get_policy().set_entry_factory(entry_factory)


def get_entry_factory():
    '''Get the global policy's entry_factory'''

    return get_policy().get_entry_factory()


def encode_data(data):
    '''Uses the global policy's data_encoder to encode_data.

    Same as:
        get_data_encoder()(data)
    '''

    return get_data_encoder()(data)


def decode_data(data):
    '''Uses the global policy's data_decoder to decode_data.

    Same as:
        get_data_decoder()(data)
    '''

    return get_data_decoder()(data)


class InvalidTag(Exception): pass


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
        str: {root}/{get_data_path()}/tag_{tag}
    '''

    return util.unipath(root, get_data_root(), 'tag_' + tag)


def get_entry(root):
    '''Get an Entry instance. This is the only way you should get Entry
    objects. This uses the global EntryFactory to retrieve an Entry object.
    Both fsfs.SimpleEntryFactory and fsfs.EntryFactory maintain a cache of
    Entry instances, so this function will always return the same Entry
    instance given the same path.

    Arguments:
        root (str): Directory

    Returns:
        Entry: created by the global policy's entry_factory
    '''

    return get_entry_factory()(root)


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


def read_blob(root, key):
    '''Get a File object for the specified blob in the directory metadata

    Arguments:
        root (str): Directory containing metadata
        key (str): Name of blob to retrieve

    Returns:
        File: used to open and read the blob
    '''

    entry = get_entry(root)
    return entry.read_blob(*keys)


def write_blob(root, key, data):
    '''Write binary blob to the directory metadata

    Arguments:
        root (str): Directory to write to
        key (str): Key used to store blob
        data (str or bytes): binary data

    Returns:
        None
    '''

    entry = get_entry(root)
    entry.write_blob(key, data)


def read_file(root, *keys):
    '''Get a File object for the specified file in the directory metadata

    Arguments:
        root (str): Directory containing metadata
        key (str): Name of file to retrieve

    Returns:
        File: used to open and read the file
    '''

    entry = get_entry(root)
    return entry.read_file(*keys)


def write_file(root, key, file):
    '''Write file to the directory metadata

    Arguments:
        root (str): Directory to write to
        key (str): Key used to store file
        file (str): Full path to a file

    Returns:
        None
    '''

    entry = get_entry(root)
    entry.write_file(key, file)


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


def get_tags(root):
    '''Get the directory's tags

    Arguments:
        root (str): Directory to get tags from

    Returns:
        list: List of tags
    '''

    tags = []
    try:
        for entry in scandir(util.unipath(root, get_data_root())):
            if entry.name.startswith('tag_'):
                tags.append(entry.name.replace('tag_', ''))
    except OSError as e:
        if e.errno != errno.ESRCH:
            raise
    return tags


def tag(root, *tags):
    '''Tag a directory as an Entry with the provided tags.

    Arguments:
        root (str): Directory to tag
        *tags (List[str]): Tags to add to directory like: 'asset' or 'project'
    '''
    if not tags:
        raise Exception('Must provide at least one tag.')

    entry = get_entry(util.unipath(root))
    entry.tag(*tags)


def untag(root, *tags):
    '''Remove a tag from a directory.

    Arguments:
        root (str): Directory to remove tags from
        *tags (List[str]): Tags to remove like: 'asset' or 'project'
    '''
    if not tags:
        raise Exception('Must provide at least one tag.')

    entry = get_entry(util.unipath(root))
    entry.untag(*tags)


def search(root, tags=None, direction=DOWN, depth=0, skip_root=False):
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

    tags = util.tupilize(tags)
    [validate_tag(tag) for tag in tags]

    if direction == DOWN:

        base_level = root.count(os.sep)
        for root, subdirs, _ in walk(root):

            level = root.count(os.sep) - base_level

            if depth and level == depth:
                del subdirs[:]

            subdirs[:] = [d for d in subdirs if not d == get_data_root()]

            if skip_root and level == 0:
                continue

            if is_match(root, *tags):
                yield get_entry(util.unipath(root))

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
        return os.path.isdir(util.unipath(root, get_data_root()))

    match = True
    for tag in tags:
        tag_path = make_tag_path(root, tag)
        if not os.path.isfile(tag_path):
            match = False

    return match


def search_uuid(root, uuid, direction=DOWN, depth=0, skip_root=False):
    '''Like search but finds a uuid file instead of a tags. Used to relink
    moved entries.

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

            subdirs[:] = [d for d in subdirs if not d == get_data_root()]

            if skip_root and level == 0:
                continue

            root = util.unipath(root)
            data_root = util.unipath(root, get_data_root())
            uuid_file = util.unipath(root, get_data_root(), 'uuid_' + uuid)
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

            data_root = util.unipath(root, get_data_root())
            uuid_path = util.unipath(root, get_data_root(), 'uuid_' + uuid)
            if os.path.isfile(uuid_path):
                yield root, data_root, uuid_file

            next_root = os.path.dirname(root)
            if next_root == root:
                break


def one_uuid(*args, **kwargs):
    '''Return first result from search_uuid.

    See also:
        :func:`fsfs.api.search_uuid`

    Returns:
        tuple: (root, data_root, uuid_file)
    '''

    matches = search_uuid(*args, **kwargs)
    try:
        return matches.next()
    except StopIteration:  # no result
        return

