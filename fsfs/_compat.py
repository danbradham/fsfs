# -*- coding: utf-8 -*-
from __future__ import absolute_import


try:
    callable = callable
except NameError:
    callable = lambda obj: hasattr(obj, '__call__')

try:
    basestring = basestring
except NameError:
    basestring = (str, bytes)

try:
    from itertools import izip
except ImportError:
    izip = zip
