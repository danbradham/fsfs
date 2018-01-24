# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__all__ = [
    'channel',
    'EntryMoved',
    'EntryDataChanged',
    'EntryTagged',
    'EntryMissing',
]

from fsfs import signal


channel = signal.Channel()
EntryCreated = channel.signal('entry.created')
EntryMoved = channel.signal('entry.moved')
EntryTagged = channel.signal('entry.data.tagged')
EntryUntagged = channel.signal('entry.data.untagged')
EntryMissing = channel.signal('entry.missing')
EntryRelinked = channel.signal('entry.relinked')
EntryDeleted = channel.signal('entry.deleted')
EntryDataChanged = channel.signal('entry.data.changed')
EntryDataDeleted = channel.signal('entry.data.deleted')
EntryUUIDChanged = channel.signal('entry.uuid.changed')
