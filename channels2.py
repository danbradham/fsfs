# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function
from collections import defaultdict
import inspect
import weakref


class WeakRef(weakref.ref):
    pass


class WeakMeth(object):

    def __init__(self, obj, callback=None):
        self.name = obj.__name__
        self.ref = WeakRef(obj.__self__, callback)

    def __call__(self):
        inst = self.ref()
        if inst is None:
            return
        return getattr(inst, self.name)


class WeakSet(object):

    def __init__(self):
        self._refs = []
        self._ids = []

    def __len__(self):
        return len(self._ids)

    def __contains__(self, obj):
        return (
            obj in self._ids or
            obj in self._refs or
            self._ref_id(obj) in self._ids
        )

    def __iter__(self):
        for ref in self._refs:
            obj = ref()
            if obj is None:
                continue
            yield obj

    def _ref_id(self, obj):
        if inspect.ismethod(obj):
            return (id(obj.__self__), id(obj.__func__))
        else:
            return id(obj)

    def _cleanup_ref(self, ref):
        ref_id = ref.ref_id
        if ref_id not in self._ids:
            return

        index = self._ids.index(ref_id)
        self._ids.pop(index)
        self._refs.pop(index)

    def add(self, obj):
        ref_id = self._ref_id(obj)
        if ref_id in self._ids:
            return

        self._ids.append(ref_id)
        if inspect.ismethod(obj):
            ref = WeakMeth(obj, self._cleanup_ref)
            ref.ref.ref_id = ref_id
        else:
            ref = WeakRef(obj, self._cleanup_ref)
            ref.ref_id = ref_id

        self._refs.append(ref)

    def discard(self, obj):
        ref_id = self._ref_id(obj)
        if ref_id not in self._ids:
            return

        index = self._ids.index(ref_id)
        self._ids.pop(index)
        self._refs.pop(index)


class Dispatcher(object):
    '''Called by a channel to dispatch a message to a receiver. The default
    dispatcher simply executes the receiver passing along the args and kwargs
    passed to Channel.send.

    The purpose of the Dispatcher class is to allow users to override the
    execution behavior of Channel receivers. For example in a Qt application,
    a user may want to execute the receiver in the main thread, or queue the
    receiver in the main event loop and await the result.
    '''

    def dispatch(self, receiver, *args, **kwargs):
        return receiver(*args, **kwargs)


DEFAULT_DISPATCHER = Dispatcher()


class Band(object):
    '''A collection of Channels. A Channel in one band, will not receiver
    signals from another band. You can override the execution behavior of
    receivers by providing your own Dispatcher with a dispatch method.

    A band will always return the same Channel instance for a given identifier
    and parent. However, Band stores only weakrefs to Channels, so if you're
    channel goes out of scope, it will be deleted and any receivers will be
    lost.

    Arguments:
        dispatcher: Dispatcher object with a dispatch method
    '''

    def __init__(self, dispatcher=None):
        self.dispatcher = dispatcher or DEFAULT_DISPATCHER
        self.channels = {}
        self.by_parent = defaultdict(dict)
        self.by_identifier = defaultdict(set)

    def _cleanup_channel(self, ref):
        '''Cleanup a channel after it's reference dies'''

        identifier, parent_id = ref.key
        self.by_identifier[identifier].discard(ref.key)
        self.by_parent[parent_id].pop(identifier, None)
        self.channels.pop(ref.key, None)

    def dispatch(self, receiver, *args, **kwargs):
        '''Executes a receiver using this Band's dispatcher'''

        return self.dispatcher.dispatch(receiver, *args, **kwargs)

    def get_channel_receivers(self, chan):
        '''Get all receivers for the provided channel.

        If the channel is bound, yield the bound Channel's receivers
        plus any anonymous receivers connected to an unbound Channel with the
        same identifier.

        If the channel is unbound, yield receivers connected to all unbound
        and bound Channels with the same identifier.
        '''

        if chan.bound:
            yield chan.receivers
            key = chan.identifier, id(None)
            if key in self.channels:
                any_chan = self.channels[(chan.identifier, id(None))]()
                if any_chan:
                    yield any_chan.receivers
        else:
            yield chan.receivers
            for key in self.by_identifier[chan.identifier]:
                other_chan = self.channels[key]()
                if other_chan is chan:
                    continue
                yield other_chan.receivers

    def channel(self, identifier, parent=None):
        '''Get a Channel instance for the provided identifier. If a parent is
        provided return a bound Channel, otherwise return an unbound Channel

        Arguments:
            identifier (str): Identifier of Channel like "started"
            parent (obj): Parent to bind Channel to

        Returns:
            unbound or bound Channel
        '''

        key = (identifier, id(parent))
        if key not in self.channels:
            chan = Channel(identifier, parent, self)
            ref = WeakRef(chan, self._cleanup_channel)
            ref.key = key
            self.channels[key] = ref
            self.by_parent[id(parent)][identifier] = key
            self.by_identifier[identifier].add(key)
        return self.channels[key]()


DEFAULT_BAND = Band()
ACTIVE_BAND = DEFAULT_BAND


def get_band():
    '''Get the currently active Band'''

    return ACTIVE_BAND


def use_default_band():
    '''Set the active band to the default band'''

    global ACTIVE_BAND
    ACTIVE_BAND = DEFAULT_BAND


def use_band(band):
    '''Set the active band to the provided band'''

    global ACTIVE_BAND
    ACTIVE_BAND = band


def channel(identifier, parent=None, band=None):
    '''Get a Channel instance for the provided identifier in the active band.
    If a parent is provided return a bound Channel, otherwise return an
    unbound Channel.

    Arguments:
        identifier (str): Identifier of Channel like "started"
        parent (obj): Parent to bind Channel to

    Returns:
        unbound or bound Channel
    '''

    band = band or ACTIVE_BAND
    return band.channel(identifier, parent)


def send(identifier, *args, **kwargs):
    '''Send a message to a Channel with the given identifier and parent in
    the active band. If no parent is provided, broadcasts *args and **kwargs
    to all unbound and bound receivers for identifier.

    Arguments:
        identifier (str): Identifier of Channel like "started"
        parent (obj): Parent to bind Channel to

    Returns:
        list of results
    '''

    parent = kwargs.pop('parent', None)
    band = kwargs.pop('parent', ACTIVE_BAND)
    return band.channel(identifier, parent).send(*args, **kwargs)


class Channel(object):
    '''A Channel which users can use to send messages to connected receivers.

    In literal terms, a Channel is a registry of functions that get called
    in the order they were connected to a Channel instance. Typically users
    do not create Channel instances manually, they use the :func:`channel` to
    create Channels in the active Band or use :meth:`Band.channel` to
    explicitly create a Channel in a Band.

    A Channel can be unbound (anonymous) or bound to an object. When messages
    are sent through an unbound Channel, they are broadcast to unbound and
    bound receivers for the Channel's identifier. When sent through a bound
    Channel, messages are sent only to the bound Channel's receivers and any
    receivers connected to the unbound Channel with the same identifier.

    Channel objects are also descriptors. When used as a class attribute, the
    Channel will become bound upon first access.
    '''

    def __init__(self, identifier, parent=None, band=None):
        self.identifier = identifier
        if parent:
            self.parent = weakref.proxy(parent)
        else:
            self.parent = parent
        self.band = band or get_band()
        self.receivers = WeakSet()

    def __get__(self, obj, type):
        if obj is None:
            return self

        chan = self.band.channel(self.identifier, obj)

        # Bind this descriptor to the class instance
        for name, member in inspect.getmembers(type):
            if member is self:
                setattr(obj, name, chan)

        return chan

    def __repr__(self):
        return '<{} {} at 0x{}>(identifier={!r})'.format(
            ('unbound', 'bound')[self.bound],
            self.__class__.__name__,
            id(self),
            self.identifier
        )

    def get_receivers(self):
        for receivers in self.band.get_channel_receivers(self):
            for receiver in receivers:
                yield receiver

    @property
    def bound(self):
        return self.parent is not None

    def send(self, *args, **kwargs):
        return [
            self.band.dispatch(receiver, *args, **kwargs)
            for receiver in self.get_receivers()
        ]

    def connect(self, obj):
        self.receivers.add(obj)

    def disconnect(self, obj):
        self.receivers.discard(obj)


def is_channel(obj):
    return isinstance(obj, Channel)
