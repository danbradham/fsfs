# -*- coding: utf-8 -*-
from __future__ import print_function, absolute_import
__all__ = [
    'Entry',
    'EntryData',
]
import os
import shutil
import errno
from scandir import scandir
from fsfs import api, util


class EntryData(object):
    '''Interface to a directories metadata and tags.'''

    def __init__(self, path):
        self.path = util.unipath(path, api.DATA_ROOT)
        self.file = util.unipath(self.path, api.DATA_FILE)
        self._tags = []
        self._data = None
        self._data_mtime = None

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

    def _init(self):
        if not os.path.isfile(self.file):
            util.touch(self.file)

    def _read(self):
        '''Ensure data directory is initialized, then read or update cache'''

        self._init()
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
                self._data = api.DATA_DECODER(raw_data)
            self._data_mtime = mtime

        return self._data

    def _write(self, **data):
        '''Ensure data directory is initialized, then write updated data'''

        self._init()
        new_data = self._read()
        util.update_dict(new_data, data)

        with open(self.file, 'w') as f:
            f.write(api.DATA_ENCODER(new_data))

        self._data = new_data
        self._data_mtime = os.path.getmtime(self.file)

    def _tag_path(self, tag):
        return util.unipath(self.path, 'tag_' + tag)

    @property
    def itags(self):
        for entry in scandir(self.path):
            if entry.name.startswith('tag_'):
                yield entry.name.replace('tag_', '')

    @property
    def tags(self):
        return list(self.itags)

    def tag(self, tag):
        api.validate_tag(tag)

        tag_path = self._tag_path(tag)
        if os.path.isfile(tag_path):
            return

        util.touch(tag_path)

    def untag(self, tag):
        api.validate_tag(tag)

        tag_path = self._tag_path(tag)
        if os.path.isfile(tag_path):
            os.remove(tag_path)

    def read(self, *keys):
        data = self._read()

        if not keys:
            return data

        if len(keys) == 1:
            return data[keys[0]]

        return dict((k, data[k]) for k in keys)

    def write(self, **data):
        self._write(**data)

    def delete(self):
        try:
            shutil.rmtree(self.path)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise


class Entry(object):
    '''Represents a directory with metadata and tags.'''

    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        self.data = EntryData(path)

    def __repr__(self):
        return '<fsfs.Entry>(name={name}, path={path})'.format(**self.__dict__)

    def __str__(self):
        return self.path

    @property
    def tags(self):
        return self.data.tags

    def tag(self, tag):
        self.data.tag(tag)

    def untag(self, tag):
        self.data.untag(tag)

    def read(self, *keys):
        return self.data.read(*keys)

    def write(self, **data):
        self.data.write(**data)

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
        super(Entry, self).delete()
        if remove_root:
            try:
                shutil.rmtree(self.path)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
