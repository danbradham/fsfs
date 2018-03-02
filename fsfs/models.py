# -*- coding: utf-8 -*-
from __future__ import print_function, absolute_import
__all__ = [
    'Entry',
    'EntryData',
]
import os
import shutil
import errno
import yaml
import uuid
from collections import defaultdict
from functools import wraps
from scandir import scandir
from fsfs import api, util, lockfile, types, signals, _search


class EntryNotFoundError(Exception): pass


def relink_uuid(entry):
    '''Search for entry by uuid and relink the entry and entry_data to the
    newly found path.

    Arguments:
        entry (Entry): the entry to attempt to relink

    Returns:
        None

    Raises:
        Exception: when relink fails
    '''

    data = entry.data
    if os.path.isdir(data.path):
        # uuid changed
        uuid_info = data._get_uuid(data.path)
        if uuid_info:
            data.uuid, data.uuid_file = uuid_info
            return
        # uuid file deleted
        data._new_uuid()
        return

    if os.path.isdir(entry.path):
        # Data directory no longer exists
        exc = EntryNotFoundError(
            'Entry data directory no longer exists: ' + data.path
        )
        signals.EntryMissing.send(entry, exc)
        raise exc

    match = None

    # Find parent directory. Quickest way to handle renamed entry
    level = 1
    root = os.path.dirname(entry.path)
    while not os.path.isdir(root):
        root = os.path.dirname(root)
        level += 1
        if level >= 10:
            exc = EntryNotFoundError(
                'File system branch containing Entry no longer exists...'
            )
            signals.EntryMissing.send(entry, exc)
            raise exc

    match = _search.one_uuid(root, data.uuid, depth=level + 1)

    # Search top-level parent entry
    if not match:
        try:
            parent = list(entry.parents())[-1]
            match = _search.one_uuid(parent.path, data.uuid)
        except IndexError:
            pass

    if match:
        old_root = entry.path
        new_root, new_data_root, new_uuid_file = match
        entry._set_path(new_root, data.uuid, new_uuid_file)
        signals.EntryRelinked.send(entry, old_root, new_root)
    else:
        exc = EntryNotFoundError(
            'Could not locate Entry matching uuid: ' + data.uuid +
            '    Entry: ' + repr(entry)
        )
        signals.EntryMissing.send(entry, exc)
        raise exc


class EntryData(object):
    '''Interface to a directories metadata and tags.'''

    def __init__(self, parent, path):
        self.parent = parent

        # Setup data paths
        self.path = None
        self.blobs_path = None
        self.files_path = None
        self.file = None
        self.uuid = None
        self.uuid_file = None
        self._lock = None
        self._set_path(path)

        self._data = None
        self._data_mtime = None

    def _set_path(self, path, uuid=None, uuid_file=None):
        self.path = path
        self.blobs_path = util.unipath(self.path, 'blobs')
        self.files_path = util.unipath(self.path, 'files_path')
        self.file = util.unipath(self.path, api.get_data_file())

        if not uuid or not uuid_file:
            self.uuid = None
            self.uuid_file = None
            self._find_uuid()
        else:
            self.uuid = uuid
            self.uuid_file = uuid_file

        if self._lock and self._lock.acquired:
            self._lock.release()

        self._lock = lockfile.LockFile(util.unipath(self.path, '.lock'))

    # Act like a dict

    def __repr__(self):
        return self._read().__repr__()

    def __str__(self):
        return self._read().__str__()

    def __getitem__(self, key):
        return self._read()[key]

    def __delitem__(self, key):
        data = self._read()
        del data[key]
        signals.EntryDataChanged.send(self.parent, dict(self._data))

    def __setitem__(self, key, value):
        self._write(**{key: value})
        signals.EntryDataChanged.send(self.parent, dict(self._data))

    def __iter__(self):
        return self._read().__iter__()

    def __contains__(self, key):
        return key in self._read()

    def __len__(self):
        return self._read().__len__()

    def keys(self):
        return self._read().keys()

    def items(self):
        return self._read().items()

    def values(self):
        return self._read().values()

    def get(self, *args):
        return self._read().get(*args)

    def update(self, **kwargs):
        self._write(**kwargs)
        signals.EntryDataChanged.send(self.parent, dict(self._data))

    def __eq__(self, other):
        self._read().__eq__(other)

    def __ne__(self, other):
        self._read().__ne__(other)

    # Core Methods

    def _make_uuid_path(self, uuid):
        return util.unipath(self.path, 'uuid_' + uuid)

    def _get_uuid(self, path):
        for entry in scandir(path):
            if entry.name.startswith('uuid_'):
                return entry.name.replace('uuid_', ''), entry.name

    def _find_uuid(self):

        if not os.path.isdir(self.path):
            return False

        for entry in scandir(self.path):
            if entry.name.startswith('uuid_'):
                self.uuid = entry.name.replace('uuid_', '')
                self.uuid_file = entry.path
                return True

    def _new_uuid(self):
        '''Use this at your own risk. UUID is used for Entry rediscovery.
        If you change it other processes will become out of sync.
        '''

        is_new_uuid = bool(self.uuid)

        with self._lock:

            if self.uuid_file and os.path.isfile(self.uuid_file):
                os.remove(self.uuid_file)

            self.uuid = str(uuid.uuid4())
            self.uuid_file = self._make_uuid_path(self.uuid)
            util.touch(self.uuid_file)

        if is_new_uuid:
            signals.EntryUUIDChanged.send(self.parent)

    def _init_uuid(self):
        if self.uuid:
            return
        if self._find_uuid():
            return
        self._new_uuid()

    def _init(self):
        if self.uuid and not os.path.isfile(self.uuid_file):
            relink_uuid(self.parent)

        is_new = False
        if not os.path.isfile(self.file):
            util.touch(self.file)
            is_new = True

        self._init_uuid()

        if is_new:
            signals.EntryCreated.send(self.parent)

    def _read(self):
        '''Ensure data directory is initialized, then read or update cache'''

        self._init()

        with self._lock:
            mtime = os.path.getmtime(self.file)
            needs_update = (
                self._data is None or
                self._data_mtime < mtime
            )

            if needs_update:

                with open(self.file, 'r') as f:
                    raw_data = f.read()

                if not raw_data:
                    self._data = {}
                else:
                    self._data = api.decode_data(raw_data)

                self._data_mtime = mtime

            return self._data

    def _write(self, replace=False, **data):
        '''Ensure data directory is initialized, then write updated data'''

        self._init()

        with self._lock:
            if not replace:
                new_data = self._read()
                util.update_dict(new_data, data)
            else:
                new_data = data
            with open(self.file, 'w') as f:
                f.write(api.encode_data(new_data))

            self._data = new_data
            self._data_mtime = os.path.getmtime(self.file)

    def _make_tag_path(self, tag):
        return util.unipath(self.path, 'tag_' + tag)

    @property
    def itags(self):
        for entry in scandir(self.path):
            if entry.name.startswith('tag_'):
                yield entry.name.replace('tag_', '')

    @property
    def tags(self):
        return list(self.itags)

    def tag(self, *tags):
        self._init()
        for tag in tags:
            api.validate_tag(tag)
            tag_path = self._make_tag_path(tag)
            if not os.path.isfile(tag_path):
                util.touch(tag_path)

        signals.EntryTagged.send(self.parent, tags)

    def untag(self, *tags):
        for tag in tags:
            api.validate_tag(tag)
            tag_path = self._make_tag_path(tag)
            if os.path.isfile(tag_path):
                os.remove(tag_path)

        signals.EntryUntagged.send(self.parent, tags)

    def read(self, *keys):
        data = self._read()

        if not keys:
            return data

        if len(keys) == 1:
            return data[keys[0]]

        return dict((k, data[k]) for k in keys)

    def write(self, replace=False, **data):
        self._write(replace, **data)
        signals.EntryDataChanged.send(self.parent, dict(self._data))

    def remove(self, *keys):
        data = self._read()
        for key in keys:
            data.pop(key, None)
        self._write(replace=True, **data)
        signals.EntryDataChanged.send(self.parent, dict(self._data))

    def read_blob(self, key):
        data = self._read()
        blobs = data.setdefault('blobs', {})
        blob_path = util.unipath(self.blobs_path, blobs[key])
        return types.File(blob_path, mode='rb')

    def write_blob(self, key, data):
        if not os.path.exists(self.blobs_path):
            os.makedirs(self.blobs_path)

        blob_name = key + '.blob'
        with open(util.unipath(self.blobs_path, blob_name), 'wb') as f:
            f.write(data)

        self._write(**dict(blobs={key: blob_name}))
        signals.EntryDataChanged.send(self.parent, dict(self._data))

    def read_file(self, key):
        data = self._read()
        files = data.setdefault('files', {})
        file_path = util.unipath(self.files_path, files[key])
        return types.File(file_path, mode='rb')

    def write_file(self, key, file):
        if not os.path.exists(self.files_path):
            os.makedirs(self.files_path)

        file_name = os.path.basename(file)
        file_path = util.unipath(self.files_path, file_name)
        util.copy_file(file, file_path)

        self._write(**dict(files={key: file_name}))
        signals.EntryDataChanged.send(self.parent, dict(self._data))

    def delete(self):
        try:
            shutil.rmtree(self.path)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        signals.EntryDataDeleted.send(self.parent)


class Entry(object):
    '''Represents a directory with metadata and tags.'''

    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        self.data = EntryData(self, util.unipath(path, api.get_data_root()))

    def __repr__(self):
        return '<fsfs.Entry>(name={name}, path={path})'.format(**self.__dict__)

    def __str__(self):
        return self.path

    def _set_path(self, path, uuid=None, uuid_file=None):
        '''Sets this Entry's path. Used by relink to update this Entry's
        path, name, and it's associated data path. This shouldn't be necessary
        during normal usage.
        '''

        self.path = path
        self.name = os.path.basename(path)
        data_path = util.unipath(path, api.get_data_root())
        self.data._set_path(data_path, uuid, uuid_file)

    @property
    def uuid(self):
        '''Entry's UUID stored in a filename in the data dir uuid_*'''

        return self.data.uuid

    @property
    def tags(self):
        '''List of this Entry's tags'''

        return self.data.tags

    def tag(self, *tags):
        '''Add tags to this Entry

        Arguments:
            *tags
        '''
        self.data.tag(*tags)

    def untag(self, *tags):
        '''Remove tags from this Entry

        Arguments:
            *tags
        '''
        self.data.untag(*tags)

    def read(self, *keys):
        '''Read this Entry's data

        Arguments:
            *keys: If specified, the returned dict will only contain these keys
                   If only one key is passed, return just the value for that
                   key and not a dict

        Returns:
            dict or value
        '''
        return self.data.read(*keys)

    def write(self, replace=False, **data):
        '''Write data to this Entry

        Arguments:
            **data: key, value pairs to write to the Entry's data
        '''

        self.data.write(replace, **data)

    def remove(self, *keys):
        '''Remove keys from this Entry's data

        Arguments:
            *keys: Keys to remove from data
        '''

        self.data.remove(*keys)

    def read_blob(self, key):
        '''Get a file object representing a blob stored under the specified key

        Arguments:
            key: blob's key

        Returns:
            `fsfs.File` object
        '''

        return self.data.read_blob(key)

    def write_blob(self, key, data):
        '''Write binary data under the specified key. This will store the data
        in a file under the "blobs" subdirectory. You can then get a handle
        to the blob file via `Entry.read_blob(key)`.

        Arguments:
            key: blob's key
            data: binary data
        '''

        self.data.write_blob(key, data)

    def read_file(self, key):
        '''Get a File stored under the specified key

        Arguments:
            key: file's key

        Returns:
            `fsfs.File` object
        '''

        return self.data.read_file(key)

    def write_file(self, key, file):
        '''Write a file under the specified key. This will copy the file to
        the "files" subdirectory. You can then get a handle to the file via
        `Entry.read_file(key)`.

        Arguments:
            key: files's key
            file: path to file
        '''

        self.data.write_file(key, file)

    def parents(self, *tags):
        '''Walks up the directory tree yielding Entry objects. If tags are
        provided, only Entry's matching those keys will be yieled

        Arguments:
            *tags

        Returns:
            generator: Entry objects
        '''
        g = api.search(self.path, direction=api.UP, skip_root=True)
        if tags:
            g = g.tags(*tags)
        return g

    def parent(self, *tags):
        '''Walks up the directory tree returning the first Entry object found.
        If tags are provided, only an Entry matching those keys will be
        returned.

        Arguments:
            *tags

        Returns:
            Entry: parent of this Entry
        '''

        g = api.search(self.path, direction=api.UP, skip_root=True)
        if tags:
            g = g.tags(*tags)
        return g.one()

    def children(self, *tags):
        '''Walks down the directory tree yielding Entry objects. If tags are
        provided, only Entry's matching those keys will be yieled

        Arguments:
            *tags

        Returns:
            generator: Entry objects
        '''
        g = api.search(self.path, skip_root=True)
        if tags:
            g = g.tags(*tags)
        return g

    @property
    def exists(self):
        '''An Entry exists when it's path exists and it's data path exists'''

        return os.path.isdir(self.path) and os.path.isdir(self.data.path)

    def copy(self, dest, only_data=False):
        '''Copy this Entry and it's children to a new location

        Arguments:
            dest (str): Destination path for new Entry
            only_data (bool): Copy only Entry data, includes no files outside
                the Entry's data directories

        Raises:
            OSError: Raised when dest already exists or copy_tree fails.
                Entry is left in original location, any files partially copied
                will be removed.

        '''

        if os.path.exists(dest):
            raise OSError('Can not copy Entry to existing location...')

        try:
            if not only_data:
                util.copy_tree(self.path, dest, force=True, overwrite=True)
            else:
                hierarchy = [self] + list(self.children())
                for entry in hierarchy:
                    old_data_path = entry.data.path
                    rel_data_path = os.path.relpath(old_data_path, self.path)
                    new_data_path = util.unipath(dest, rel_data_path)
                    util.copy_tree(old_data_path, new_data_path)
        except:
            if os.path.exists(dest):
                shutil.rmtree(dest)
            raise

        # Update uuids and send EntryCreated signals
        new_entry = api.get_entry(dest)
        new_entry.data._new_uuid()
        signals.EntryCreated.send(new_entry)
        for child in new_entry.children():
            child.data._new_uuid()
            signals.EntryCreated.send(child)
        return new_entry

    def move(self, dest):
        '''Move this Entry and it's children to a new location

        Arguments:
            dest (str): Destination path for new Entry

        Raises:
            OSError: Raised when dest already exists or move_tree fails.
                Entry is left in original location, any files partially copied
                will be removed.
        '''

        if os.path.exists(dest):
            raise OSError('Can not move Entry to existing location...')

        # Recurisvely moves the tree
        try:
            util.move_tree(self.path, dest, force=True, overwrite=True)
        except:
            if os.path.exists(dest):
                shutil.rmtree(dest)
            raise

        # Update uuids and send EntryCreated signals
        old_path = self.path
        new_path = dest
        self._set_path(dest)  # Update this Entry's path
        signals.EntryMoved.send(self, old_path, new_path)
        for child in self.children():
            new_child_path = child.path
            old_child_path = new_child_path.replace(new_path, old_path)
            signals.EntryMoved.send(child, old_child_path, new_child_path)

    def delete(self, remove_root=False):
        '''Delete an entry

        Arguments:
            remove_root (bool): Remove root directory and all it's contents not
                just the data directory that marks this as an Entry
        '''

        self.data.delete()

        if remove_root:
            # Delete children depth-first making sure we send all
            # appropriate signals along the way
            for child in list(self.children())[::-1]:
                child.delete(remove_root=remove_root)

            try:
                shutil.rmtree(self.path)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise

        signals.EntryDeleted.send(self.parent)
