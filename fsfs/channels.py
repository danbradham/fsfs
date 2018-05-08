# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__all__ = [
    'band',
    'EntryCreated',
    'EntryMoved',
    'EntryTagged',
    'EntryUntagged',
    'EntryMissing',
    'EntryRelinked',
    'EntryDeleted',
    'EntryDataChanged',
    'EntryDataDeleted',
    'EntryUUIDChanged',
    'transfer_receivers',
    'IDENTIFIERS'
]

from bands import Band


band = Band()
EntryCreated = band.channel('entry.created')
EntryMoved = band.channel('entry.moved')
EntryTagged = band.channel('entry.data.tagged')
EntryUntagged = band.channel('entry.data.untagged')
EntryMissing = band.channel('entry.missing')
EntryRelinked = band.channel('entry.relinked')
EntryDeleted = band.channel('entry.deleted')
EntryDataChanged = band.channel('entry.data.changed')
EntryDataDeleted = band.channel('entry.data.deleted')
EntryUUIDChanged = band.channel('entry.uuid.changed')

IDENTIFIERS = [
    'entry.created'
    'entry.moved'
    'entry.data.tagged'
    'entry.data.untagged'
    'entry.missing'
    'entry.relinked'
    'entry.deleted'
    'entry.data.changed'
    'entry.data.deleted'
    'entry.uuid.changed'
]

# TODO: Implement sqlite dispatcher to facility IPC

def transfer_receivers(src, dest):
    '''Transfers channel receivers from one object to another.'''

    for identifier in IDENTIFIERS:
        src_channel = band.channel(identifier, src)
        dest_channel = band.channel(identifier, dest)
        for receiver in src_channel.receivers:
            dest_channel.connect(receiver)
