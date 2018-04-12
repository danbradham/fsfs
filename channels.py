# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function
'''
Is this worth the effort?
'''
from collections import defaultdict
import inspect
import weakref


try:
    basestring
except NameError:
    basestring = str


ANY = 'ANY'


class reference(weakref.ref):
    pass


class WeakList(object):
    '''Like WeakList but works with bound methods'''

    def __init__(self):
        self._ids = []
        self._refs = []

    def __repr__(self):
        return (
            '<{}>(_ids={}, _refs={})'
        ).format(
            self.__class__.__name__,
            self._ids,
            self._refs
        )

    def __len__(self):
        return len(self._refs)

    def __iter__(self):
        for i in range(len(self._refs)):
            ref_id = self._ids.pop(0)
            ref = self._refs.pop(0)
            obj = ref()
            if obj is not None:
                yield obj
                self._refs.append(ref)
                self._ids.append(ref_id)

    def _cleanup_ref(self, ref):
        ref_id = ref.reference_id
        if ref_id not in self._ids:
            return

        index = self._ids.index(ref_id)
        self._ids.pop(index)
        self._refs.pop(index)

    def remove(self, obj):
        ref_id = reference_id(obj)

        if ref_id not in self._ids:
            return

        index = self._ids.index(ref_id)
        self._ids.pop(index)
        self._refs.pop(index)

    def append(self, obj):
        ref_id = reference_id(obj)

        if ref_id in self._ids:
            return

        self._ids.append(ref_id)

        if inspect.ismethod(obj):
            ref = weakmeth(obj, self._cleanup_ref)
            ref.ref.reference_id = ref_id
        else:
            ref = reference(obj, self._cleanup_ref)
            ref.reference_id = ref_id

        self._refs.append(ref)


class weakmeth(object):
    '''Like weakref but for bound methods'''

    def __init__(self, meth, callback=None):
        self.name = meth.__name__
        if callback:
            self.ref = reference(meth.__self__, callback)
        else:
            self.ref = reference(meth.__self__)

    def __call__(self):
        obj = self.ref()
        if obj is None:
            return
        return getattr(obj, self.name, None)


def reference_id(obj):
    if inspect.ismethod(obj):
        return (id(obj.__self__), id(obj.__func__))
    elif isinstance(obj, basestring):
        return obj
    else:
        return id(obj)


class BoundChannel(object):
    '''Like a standard Channel, but accepts an additional argument, sender.
    BoundChannels will always pass their sender to all Channel methods.

    Returned by Channel.__get__ when Channel is used as a class attribute.
    '''

    def __init__(self, channel, sender):
        self.channel = channel
        self.sender = sender

    def __getattr__(self, attr):
        return getattr(self.channel, attr)

    def __repr__(self):
        return '<{} at 0x{}>(identifier={!r}, sender={!r})'.format(
            self.__class__.__name__,
            id(self),
            self.identifier,
            self.sender
        )

    def get_receivers(self):
        self.channel.get_receivers(sender=self.sender)

    def send(self, *args, **kwargs):
        kwargs.setdefault('sender', self.sender)
        self.channel.send(*args, **kwargs)

    def clear(self):
        self.channel.clear(self.sender)

    def connect(self, obj):
        self.channel.connect(obj, sender=self.sender)

    def disconnect(self, obj):
        self.channel.disconnect(obj, sender=self.sender)


class Channel(object):

    _channels = weakref.WeakValueDictionary()

    def __new__(cls, identifier):
        if identifier not in cls._channels:
            inst = super(Channel, cls).__new__(cls, identifier)
            cls._channels[identifier] = inst
        return cls._channels[identifier]

    def __init__(self, identifier):
        self.identifier = identifier
        self._receivers = defaultdict(WeakList)
        self._senders = {}

    def __repr__(self):
        return '<{} at 0x{}>(identifier={!r}, sender={!r})'.format(
            self.__class__.__name__,
            id(self),
            self.identifier,
            ANY
        )

    def __get__(self, obj=None, type=None):
        '''When channels are assigned as class attributes, accessing them
        through a class attribute returns a BoundChannel. A BoundChannel is
        the same as a standard Channel, except that the sender is always set
        as the class instance.
        '''

        if obj is None:
            return self
        return BoundChannel(self, obj)

    def get_receivers(self, sender=None):
        '''Get receivers for the specified sender. If no sender is provided,
        get all receivers in the chanenl.
        '''

        sender = sender or ANY
        sender_id = reference_id(sender)

        if sender is ANY:
            all_receivers = self._receivers.values()
            if all_receivers:
                return [r for receivers in all_receivers for r in receivers]
            else:
                return all_receivers

        return list(self._receivers[sender_id]) + list(self._receivers[ANY])

    def send(self, *args, **kwargs):
        '''Send a message to all receivers in the channel. The default
        behavior is to send a message to receivers of ANY sender. You may send
        messages along to receivers of just one sender by specifying the sender
        as a keyword argument.
        '''

        sender = kwargs.pop('sender', ANY)
        return [
            receiver(sender, *args, **kwargs)
            for receiver in self.get_receivers(sender)
        ]

    def clear(self, sender=None):
        '''Clear all receivers in the channel. The default behavior is to
        clear all receivers. You may pass a sender if you'd like to clear
        receivers for just one sender.
        '''

        sender = sender or ANY
        sender_id = reference_id(sender)

        if sender is ANY:
            self._receivers = defaultdict(set)
        else:
            self._receivers.pop(sender_id, None)
            self._senders.pop(sender_id, None)

    def connect(self, obj, sender=None):
        '''Set an obj to receive messages from this channel. The default
        behavior is to connect the obj to receive messages from ANY sender.
        You may pass a sender if you'd like to have the obj receive messages
        from just one sender.
        '''

        sender = sender or ANY
        sender_id = reference_id(sender)

        if sender is not ANY and sender_id not in self._senders:
            ref = reference(sender, self._cleanup_sender)
            ref.reference_id = sender_id
            self._senders[sender_id] = ref

        self._receivers[sender_id].append(obj)

    def disconnect(self, obj, sender=None):
        '''Disconnect an obj from the channel. The default behavior is to
        remove the obj from all senders. You may pass a sender if you'd like
        to stop the obj from receiving from just that sender.
        '''

        sender = sender or ANY
        sender_id = reference_id(sender)

        if sender is not ANY and sender_id in self._receivers:
            self._receivers[sender_id].remove(obj)
        else:
            for receivers in self._receivers.values():
                receivers.remove(obj)

    def _cleanup_sender(self, ref):
        '''When a sender dies disconnect it's receivers'''

        self._receivers.pop(ref.reference_id, None)
        self._senders.pop(ref.reference_id, None)


def receiver(sender, *args, **kwargs):
    print('r', sender, args, kwargs)


def bound_receiver(sender, *args, **kwargs):
    print('br', sender, args, kwargs)


class Object(object):

    chan = Channel('channel-1')

    def __init__(self):
        self.chan.connect(self.o_bound_receiver)

    def o_bound_receiver(self, sender, *args, **kwargs):
        print('obr', sender, args, kwargs)


Object.chan.connect(receiver)
Object().chan.send(100)
Object.chan.send(200)
