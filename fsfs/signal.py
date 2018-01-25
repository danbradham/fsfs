# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__all__ = [
    'Channel',
    'Signal',
    'channel',
    'get_channel',
    'set_channel',
    'set_channel_to_default',
    'chain',
    'route',
    'send',
    'connect',
    'disconnect',
]

import uuid
from bisect import bisect_right
from collections import defaultdict, OrderedDict
from fnmatch import fnmatch
from fstrings import f

DEFAULT_PRIORITY = 0
_channels = {}
_default_channel = None
_current_channel = None


class Channel(object):
    '''Manages and sends signals by string identifier. Supports fuzzy signal
    subscriptions using fnmatch with \*. So you could connect to "new.\*" to
    subscribe to all signals that start with "new.".

    Examples:

        Basic subscription:

            >>> channel = Channel()
            >>> def subscriber():
            ...     return 'HI'
            ...
            >>> channel.connect('my.signal', subscriber)
            >>> channel.send('my.signal')
            ['HI']

        Fuzzy subscription:

            >>> channel = Channel()
            >>> @channel.route('foo.*')
            ... def foo_subscriber():
            ...     return 'FOO'
            ...
            >>> channel.send('foo.bar')
            ['FOO']
            >>> channel.send('foo.baz')
            ['FOO']

        Use a Signal alias:

            >>> channel = Channel()
            >>> my_signal = channel.signal('my.signal')
            >>> @my_signal.route()
            ... def my_subscriber():
            ...     return 'HI'
            ...
            >>> my_signal()
            ['HI']
    '''

    def __init__(self, name=None):
        self.name = name
        self.uuid = str(uuid.uuid4())
        self._subscribers = defaultdict(list)
        self._subscriber_keys = defaultdict(list)
        self._signals = {}
        self._channels = []

    def __repr__(self):
        return f('<Channel>(name={self.name}, uuid={self.uuid})')

    def __call__(self, identifier, *args, **kwargs):
        '''Shorthand for :meth:`send`'''

        return self.send(identifier, *args, **kwargs)

    def _get_forwarded_channels(self):
        channels = []
        for channel in self._channels:
            channels.append(channel)
            channels.extend(channel._get_forwarded_channels())

        return list(OrderedDict.fromkeys(channels))

    def forward(self, channel):
        '''Forwards signals to another channel

        Arguments:
            channel (Channel): Channel to forward to
        '''

        if channel in self._channels:
            return
        self._channels.append(channel)

    def unforward(self, channel):
        '''Stops forwarding signals to another channel

        Arguments:
            channel (Channel): Channel to stop forwarding signals to
        '''

        if channel not in self._channels:
            return
        self._channels.remove(channel)

    def signal(self, identifier):
        '''Get a :class:`Signal` alias that forwards all calls to this signal
        channel. Multiple calls to :meth:`signal` with the same identifier will
        return the same :class:`Signal` instance.
        '''

        if identifier not in self._signals:
            self._signals[identifier] = Signal(identifier, self)
        return self._signals.get(identifier)

    @property
    def signals(self):
        '''Return a dict containing all signal aliases.'''

        return dict(self._signals)

    def subscribers(self, identifier):
        '''Get all subscribers in order of priority for a specific signal.

        Arguments:
            identifier (str): Signal identifier

        Returns:
            list: subscribers
        '''

        subscribers = list(self._subscribers[identifier])
        subscriber_keys = list(self._subscriber_keys[identifier])

        for key in self._subscribers.keys():
            if key == identifier:
                continue

            # Incorporate fuzzy subscriptions
            if fnmatch(identifier, key):
                objs_priorities = zip(
                    self._subscribers[key],
                    self._subscriber_keys[key]
                )
                for obj, priority in objs_priorities:
                    if obj in subscribers:
                        continue
                    index = bisect_right(subscriber_keys, priority)
                    subscribers.insert(index, obj)
                    subscriber_keys.insert(index, priority)

        for channel in self._get_forwarded_channels():
            for key in channel._subscribers.keys():
                # Incorporate fuzzy subscriptions
                if key == identifier or fnmatch(identifier, key):
                    objs_priorities = zip(
                        channel._subscribers[key],
                        channel._subscriber_keys[key]
                    )
                    for obj, priority in objs_priorities:
                        if obj in subscribers:
                            continue
                        index = bisect_right(subscriber_keys, priority)
                        subscribers.insert(index, obj)
                        subscriber_keys.insert(index, priority)

        return subscribers

    def connect(self, identifier, obj, priority=DEFAULT_PRIORITY):
        '''Connect an object to a signal. Subscribers are ordered by priority.
        New subscribers are inserted after existing subscribers with the same
        priority.

        Arguments:
            identifier (str): Signal identifier
            obj (callable): Object to connect to signal
            priority (int): priority of obj
        '''

        if obj in self._subscribers[identifier]:
            return

        if not self._subscribers[identifier]:
            self._subscribers[identifier].append(obj)
            self._subscriber_keys[identifier].append(priority)
            return

        index = bisect_right(self._subscriber_keys[identifier], priority)
        self._subscribers[identifier].insert(index, obj)
        self._subscriber_keys[identifier].insert(index, priority)

    def route(self, identifier, priority=DEFAULT_PRIORITY):
        '''Connect an obj to a signal via a decoration. Only works on functions
        and callable class instances at the moment.

        Arguments:
            identifier (str): Signal identifier
            priority (int): obj priority

        Examples:
            >>> channel = Channel()
            >>> @channel.route('my.signal')
            ... def subscriber():
            ...     pass
            ...
            >>> assert subscriber in channel.subscribers('my.signal')

        '''

        def connect_to_signal(obj):
            # TODO: Support class methods using a descriptor with a get method
            #       Remove "Only works on functions"
            self.connect(identifier, obj, priority)
            return obj

        return connect_to_signal

    def disconnect(self, identifier, obj):
        '''Disconnect obj from signal

        Arguments:
            identifier (str): signal to connect obj to
            obj (callable): callable obj to connect to signal
        '''

        if obj not in self._subscribers[identifier]:
            return

        index = self._subscribers[identifier].index(obj)
        self._subscribers[identifier].pop(index)
        self._subscriber_keys[identifier].pop(index)

    def clear(self, identifier=None):
        '''Disconnect subscribers from one or all signals

        Arguments:
            identifier (str): If passed clear subscribers for just this signal

        Examples:
            Clear all signals' subscribers:

                >>> channel = Channel()
                >>> channel.clear()

            Clear one signal's subscribers:

                >>> channel = Channel()
                >>> channel.clear('my.signal')
        '''
        if not identifier:
            self._subscribers = defaultdict(list)
            self._subscriber_keys = defaultdict(list)
            return

        self._subscribers[identifier][:] = []
        self._subscriber_keys[identifier][:] = []

    def send(self, identifier, *args, **kwargs):
        '''Send a signal. Calls each subscriber with args and kwargs.

        Arguments:
            identifier (str): signal to send out
            *args: args to send
            **kwargs: kwargs to send

        Returns:
            list: contains results in order
        '''

        results = []
        for subscriber in self.subscribers(identifier):
            results.append(subscriber(*args, **kwargs))
        return results

    def chain(self, identifier, *args, **kwargs):
        '''Chain a signals subscribers. The first subscriber will be passed
        args and kwargs. Then each successive subscriber will be passed the
        return value of the previous subscriber. Unlike :meth:`send` this
        returns one value.

        Arguments:
            identifier (str): signal to send
            *args: args to send
            **kwargs: kwargs to send

        Returns:
            Final value returned from last subscriber
        '''

        subscribers = self.subscribers(identifier)
        if not subscribers:
            return

        result = subscribers[0](*args, **kwargs)
        if not len(subscribers) > 1:
            return result

        for subscriber in subscribers[1:]:
            result = subscriber(result)
        return result


class Signal(object):
    '''Alias for a Signal identifier. Forwards all calls to a parent channel
    sending the aliases identifier with it. Users should not instance Signal
    themselves, instead they should get them from a channel using the
    :meth:`signal`:

        >>> channel = Channel()
        >>> channel.signal('my.signal') # doctest: +ELLIPSIS
        Signal(channel=..., identifier='my.signal')
    '''

    def __init__(self, identifier, channel=None):
        self.identifier = identifier
        self.channel = channel or get_channel()

    def __repr__(self):
        return (
            self.__class__.__name__ + '(channel={channel}, identifier={identifier})'
        ).format(channel=self.channel, identifier=repr(self.identifier))

    def __call__(self, *args, **kwargs):
        channel = kwargs.pop('channel', self.channel)
        return channel(self.identifier, *args, **kwargs)

    def subscribers(self, **kwargs):
        channel = kwargs.pop('channel', self.channel)
        return channel.subscribers(self.identifier)

    def connect(self, obj, priority=DEFAULT_PRIORITY, **kwargs):
        channel = kwargs.pop('channel', self.channel)
        return channel.connect(self.identifier, obj, priority)

    def route(self, priority=DEFAULT_PRIORITY, **kwargs):
        channel = kwargs.pop('channel', self.channel)
        return channel.route(self.identifier, priority)

    def disconnect(self, obj, **kwargs):
        channel = kwargs.pop('channel', self.channel)
        return channel.disconnect(self.identifier, obj)

    def chain(self, *args, **kwargs):
        channel = kwargs.pop('channel', self.channel)
        return channel.chain(self.identifier, *args, **kwargs)

    def send(self, *args, **kwargs):
        channel = kwargs.pop('channel', self.channel)
        return channel.send(self.identifier, *args, **kwargs)

    def clear(self):
        channel = kwargs.pop('channel', self.channel)
        return channel.clear(self.identifier)


def get_channel():
    '''Returns global channel'''

    return _current_channel


def set_channel(channel):
    '''Sets global channel to channel'''

    global _current_channel
    _current_channel = channel


def set_channel_to_default():
    '''Sets global channel to _default_channel'''

    global _current_channel
    _current_channel = _default_channel


def channel(channel):
    '''Context manager to temporarily set signal channel'''

    global _current_channel
    _previous_channel = _current_channel
    _current_channel = channel
    try:
        yield
    finally:
        _current_channel = _previous_channel


def send(identifier, *args, **kwargs):
    '''Send signal on global channel

    Arguments:
        identifier (str): signal identifier
        channel (Channel): Channel to send on, defaults to global channel
    '''

    channel = kwargs.pop('channel', get_channel())
    return channel.send(identifier, *args, **kwargs)


def chain(identifier, *args, **kwargs):
    '''Chain signal subscribers on global channel

    Arguments:
        identifier (str): signal identifier
        channel (Channel): Channel to send on, defaults to global channel
    '''

    channel = kwargs.pop('channel', get_channel())
    return channel.chain(identifier, *args, **kwargs)


def route(identifier, *args, **kwargs):
    '''Connect function to signal via decorator

    Arguments:
        identifier (str): signal identifier
        channel (Channel): Channel to send on, defaults to global channel
    '''

    channel = kwargs.pop('channel', get_channel())
    return channel.route(identifier, *args, **kwargs)


def connect(identifier, obj, priority=DEFAULT_PRIORITY, **kwargs):
    '''Connect function to signal

    Arguments:
        identifier (str): signal identifier
        channel (Channel): Channel to send on, defaults to global channel
        priority (int): Priority of subscriber
    '''

    channel = kwargs.pop('channel', get_channel())
    channel.connect(identifier, obj, priority)


def disconnect(identifier, obj, **kwargs):
    '''Disconnect function to signal

    Arguments:
        identifier (str): signal identifier
        channel (Channel): Channel to send on, defaults to global channel
        priority (int): Priority of subscriber
    '''

    channel = kwargs.pop('channel', get_channel())
    channel.disconnect(identifier, obj)


# Create default channel
_channels['DEFAULT'] = Channel()
_default_channel = _channels['DEFAULT']
_current_channel = _default_channel
