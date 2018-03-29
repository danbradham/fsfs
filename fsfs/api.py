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
    'delete',
    'search',
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


def write(root, replace=False, **data):
    '''Write metadata to directory

    Arguments:
        root (str): Directory to write to
        **data (dict): key, value pairs to write

    Returns:
        None
    '''

    entry = get_entry(root)
    entry.write(replace, **data)


def read_blob(root, key):
    '''Get a File object for the specified blob in the directory metadata

    Arguments:
        root (str): Directory containing metadata
        key (str): Name of blob to retrieve

    Returns:
        File: used to open and read the blob
    '''

    entry = get_entry(root)
    return entry.read_blob(key)


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
    entry.delete(remove_root)


def get_tags(root):
    '''Get the directory's tags

    Arguments:
        root (str): Directory to get tags from

    Returns:
        list: List of tags
    '''

    tags = []
    path = util.unipath(root, get_data_root())
    if os.path.isdir(path):
        for entry in scandir(path):
            if entry.name.startswith('tag_'):
                tags.append(entry.name.replace('tag_', ''))
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


def search(root, direction=DOWN, depth=10, skip_root=False):
    '''Returns a Search object that yields :class:`models.Entry` objects. The
    Search generator supports advanced query functionality similar to the
    Query objects found in many SQL libraries.

    Arguments:
        root (str): Directory to search
        direction (int): Direction to search (fsfs.UP or fsfs.DOWN)
        depth (int): Maximum depth of search
        skip_root (bool): Skip search in root directory

    Examples:
        .. code-block:: python

            # Yield all entries
            search('.')

            # Get the first entry
            search('.').one()

            # Get entries by tag
            search('.').tags('project')

            # Get entries by uuid
            search('.').uuid('098a0s-asd9f-as8sf-asdf07')

            # Get entries by name
            search('.').name('entry_name')

            # Get entries by nested name
            search('.').name('parent1/parent2/entry_name')

            # Use custom predicates
            search('.').filter(lambda entry: entry.read('user') == 'Dan')

            # Combine methods to create advanced queries
            search('.').name('entry_name').tags('asset').one()
    '''

    from fsfs._search import Search
    return Search(root, direction, depth, skip_root)
