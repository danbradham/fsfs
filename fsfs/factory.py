# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
__all__ = ['RegistrationError', 'SimpleEntryFactory', 'EntryFactory']
import os
from collections import defaultdict
from fsfs import api, models, channels


class RegistrationError(Exception):
    pass


class SimpleEntryFactory(object):
    '''SimpleEntryFactory returns the base implementation of Entry.'''

    def __init__(self):
        self._cache = {}

    def __call__(self, path):
        '''Called by fsfs.get_entry via the global policy to create an entry'''

        if path not in self._cache:
            self._cache[path] = models.Entry(path)
        return self._cache[path]

    def setup(self):
        '''Connects this factory to all necessary channels. Called when this
        factory is set as the policy's entry_factory using
        :meth:`fsfs.set_entry_factory`
        '''

        channels.EntryMoved.connect(self.on_entry_relinked_or_moved)
        channels.EntryMissing.connect(self.on_entry_missing)
        channels.EntryRelinked.connect(self.on_entry_relinked_or_moved)
        channels.EntryDeleted.connect(self.on_entry_deleted)

    def teardown(self):
        '''Disconnects this factory to all necessary channels. Called when
        another factory is set as the policy's entry_factory using
        :meth:`fsfs.set_entry_factory`
        '''

        channels.EntryMoved.disconnect(self.on_entry_relinked_or_moved)
        channels.EntryMissing.disconnect(self.on_entry_missing)
        channels.EntryRelinked.disconnect(self.on_entry_relinked_or_moved)
        channels.EntryDeleted.disconnect(self.on_entry_deleted)
        self._cache.clear()

    def on_entry_relinked_or_moved(self, entry, old_path, new_path):
        '''Updates cache when entry is relinked or moved...'''

        self._cache.pop(old_path, None)
        self._cache[new_path] = entry

    def on_entry_missing(self, entry, exc):
        '''Removes entry from cache if it's missing...'''

        self._cache.pop(entry.path)

    def on_entry_deleted(self, entry):
        '''Removes entry from cache when it's deleted...'''
        print(entry)
        self._cache.pop(entry.path)


class EntryFactory(object):
    '''EntryFactory that allows you to create Entry subclasses that handle
    directories with specific tags. You could register an Entry subclass to
    handle directories with the tag "project" and provide
    additional methods.

        >>> import fsfs
        >>> factory = fsfs.EntryFactory()

        >>> class Project(factory.Entry):
        ...     def project_method(self):
        ...         print('Hello from project method')

        >>> fsfs.set_entry_factory(factory)
        >>> fsfs.tag('tmp/project', 'project')
        >>> entry = fsfs.get_entry('tmp/project')
        >>> assert type(entry.obj()) is Project

        >>> import shutil; shutil.rmtree('tmp')

    '''

    _registry = defaultdict(dict)

    def __init__(self):

        # Entry metaclass that automatically registers
        # EntryFactory.Entry subclasses
        class EntryType(type):

            def __new__(cls, name, bases, attrs):
                if name not in EntryFactory._registry[self]:
                    new_type = type.__new__(cls, name, bases, attrs)
                    type_key = attrs.setdefault('type_for_tag', name.lower())
                    EntryFactory._registry[self][type_key] = new_type
                    return new_type

                raise RegistrationError('Entry type already exists: ' + name)

        self.EntryType = EntryType

        # A subclass of fsfs.models.Entry with a type of EntryType
        # The default Entry type created by this factory
        self.Entry = self.EntryType('Entry', (models.Entry,), {})

        # Setup cache and proxy cache
        self._cache = {}
        self._mtimes = {}
        self._cache_proxies = {}

        class EntryProxy(object):
            '''This proxy is what actually gets returned by the factory. The
            proxy looks up the Entry instance stored in the _cache and
            validates it against it's tags. If the instance type does not match
            the entry's tags, a new Entry instance is created of the
            appropriate type. This is all to say that, this proxy will always
            forward attribute lookup to an Entry type that matches it's tags.
            '''

            @property
            def __class__(self):
                # force EntryProxy to work with isinstance(proxy, Entry)
                return self.factory.Entry

            def __init__(self, path, factory=self):
                self._path = path
                self.factory = factory

            def __repr__(self):
                return self.obj().__repr__()

            def __str__(self):
                return self.obj().__str__()

            def __dir__(self):
                return dir(self.obj())

            def __getattr__(self, attr):
                return getattr(self.obj(), attr)

            def obj(self):
                self.factory._update_cache(self._path, self)
                return self.factory._cache[self._path]

        self.EntryProxy = EntryProxy

    def __call__(self, path):
        '''Called by fsfs.get_entry via the global policy to create an entry'''

        self._update_cache(path)
        return self._cache_proxies[path]

    def get_type(self, tag):
        '''Get a type for the specified tag'''

        return self._registry[self][tag]

    def get_types(self):
        '''Get all registered types'''

        return self._registry[self]

    def type_for_tags(self, tags):
        '''Get the type that would be used for the specified tags'''

        for tag in tags:
            try:
                return self.get_type(tag)
            except KeyError:
                continue

        return self.Entry

    def setup(self):
        '''Connects this factory to all necessary channels. Called when this
        factory is set as the policy's entry_factory using
        :meth:`fsfs.set_entry_factory`
        '''

        channels.EntryTagged.connect(self.on_entry_tagged)
        channels.EntryUntagged.connect(self.on_entry_untagged)
        channels.EntryMoved.connect(self.on_entry_relinked_or_moved)
        channels.EntryMissing.connect(self.on_entry_missing)
        channels.EntryRelinked.connect(self.on_entry_relinked_or_moved)
        channels.EntryDeleted.connect(self.on_entry_deleted)

    def teardown(self):
        '''Disconnects this factory to all necessary channels. Called when
        another factory is set as the policy's entry_factory using
        :meth:`fsfs.set_entry_factory`
        '''

        channels.EntryTagged.disconnect(self.on_entry_tagged)
        channels.EntryUntagged.disconnect(self.on_entry_untagged)
        channels.EntryMoved.disconnect(self.on_entry_relinked_or_moved)
        channels.EntryMissing.disconnect(self.on_entry_missing)
        channels.EntryRelinked.disconnect(self.on_entry_relinked_or_moved)
        channels.EntryDeleted.disconnect(self.on_entry_deleted)
        self._cache.clear()
        self._cache_proxies.clear()
        self._mtimes.clear()

    def on_entry_tagged(self, entry, tags):
        '''When entry tag added set mtime to None. Forces proxy to update.'''

        self._mtimes[entry.path] = None

    def on_entry_untagged(self, entry, tags):
        '''When entry tag removed set mtime to None. Forces proxy to update.'''

        self._mtimes[entry.path] = None

    def on_entry_relinked_or_moved(self, entry, old_path, new_path):
        '''Update cache when entry relinked or moved'''

        _entry, proxy, _mtime = self._pop_cache_path(old_path)
        proxy._path = new_path
        tags = api.get_tags(new_path)
        entry_type = self.type_for_tags(tags)
        self._cache[new_path] = entry_type(new_path)
        self._cache_proxies[new_path] = proxy._path
        self._mtimes[new_path] = os.path.getmtime(new_path)

    def on_entry_missing(self, entry, exc):
        '''Remove entry.path from cache when entry goes missing'''

        self._pop_cache_path(entry.path)

    def on_entry_deleted(self, entry):
        '''Remove entry.path from cache when entry deleted'''

        self._pop_cache_path(entry.path)

    def _pop_cache_path(self, path):
        '''Removes the specified path from all caches'''


        return (
            self._cache.pop(path, None),
            self._cache_proxies.pop(path, None),
            self._mtimes.pop(path, None),
        )

    def _mtime_changed(self, path):
        if not os.path.isdir(path):
            return False

        return os.path.getmtime(path) != self._mtimes.get(path, None)

    def _update_cache(self, path, proxy=None):

        if path in self._cache and not self._mtime_changed(path):
            return

        tags = api.get_tags(path)
        entry_type = self.type_for_tags(tags)

        if path not in self._cache:
            self._cache[path] = entry_type(path)

        elif not type(self._cache[path]) is entry_type:
            self._cache[path] = entry_type(path)

        if path not in self._cache_proxies:
            if proxy is None:
                self._cache_proxies[path] = self.EntryProxy(path)
            else:
                self._cache_proxies[path] = proxy

        if os.path.isdir(path):
            self._mtimes[path] = os.path.getmtime(path)
