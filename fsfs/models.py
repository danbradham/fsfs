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
from fsfs import api, util, lockfile, types, signals


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

    print(root, data.uuid)
    match = api.one_uuid(root, data.uuid, depth=level + 1)
    print(match)

    # Search top-level parent entry
    if not match:
        try:
            parent = list(entry.parents())[-1]
            match = api.one_uuid(parent.path, data.uuid)
        except IndexError:
            pass

    if match:
        old_root = entry.path
        new_root, new_data_root, new_uuid_file = match
        entry.set_path(new_root, data.uuid, new_uuid_file)
        signals.EntryRelinked.send(entry, old_root, new_root)
    else:
        exc = EntryNotFoundError(
            'Could not locate Entry matching uuid: ' + data.uuid
            + '    Entry: ' + repr(entry)
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
        self.set_path(path)

        self._data = None
        self._data_mtime = None

    def set_path(self, path, uuid=None, uuid_file=None):
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

    def __setitem__(self, key, value):
        self._write(**{key: value})

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
                self.uuid_file = entry.name
                return True

    def _new_uuid(self):
        '''Use this at your own risk. UUID is used for Entry rediscovery.
        If you change it other processes will become out of sync.
        '''

        is_new_uuid = bool(self.uuid)

        with self._lock:
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
                self._data is None
                or self._data_mtime < mtime
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

    def _write(self, **data):
        '''Ensure data directory is initialized, then write updated data'''

        self._init()

        with self._lock:
            new_data = self._read()
            util.update_dict(new_data, data)

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

    def write(self, **data):
        self._write(**data)
        signals.EntryDataChanged.send(self.parent, dict(self._data))

    def read_blob(self, key):

        data = self._read()
        data.setdefault('blobs', {})
        blobs = data['blobs']
        blob_path = util.unipath(self.blobs_path, data['blobs'][key])
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
        data.setdefault('files', {})
        files = data['files']
        file_path = util.unipath(self.files_path, data['files'][key])
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

    def set_path(self, path, uuid=None, uuid_file=None):
        self.path = path
        self.name = os.path.basename(path)
        data_path = util.unipath(path, api.get_data_root())
        self.data.set_path(data_path, uuid, uuid_file)

    @property
    def tags(self):
        return self.data.tags

    def tag(self, *tags):
        self.data.tag(*tags)

    def untag(self, *tags):
        self.data.untag(*tags)

    def read(self, *keys):
        return self.data.read(*keys)

    def write(self, **data):
        self.data.write(**data)

    def read_blob(self, key):
        return self.data.read_blob(key)

    def write_blob(self, key, data):
        self.data.write_blob(key, data)

    def read_file(self, *keys):
        return self.data.read_file(*keys)

    def write_file(self, key, file):
        self.data.write_file(key, file)

    def parents(self, *tags):
        return api.search(self.path, tags, direction=api.UP, skip_root=True)

    def parent(self, *tags):
        return api.one(self.path, tags, direction=api.UP, skip_root=True)

    def children(self, *tags):
        return api.search(self.path, tags, skip_root=True)

    @property
    def exists(self):
        return os.path.isdir(self.path) and os.path.isdir(self.data.path)

    def delete(self, remove_root=False):
        self.data.delete()
        if remove_root:
            try:
                shutil.rmtree(self.path)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise

        signals.EntryDeleted.send(self.parent)
