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
