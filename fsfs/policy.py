# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

__all__ = [
    '_global_policy',
    'FsFsPolicy',
    'JsonEncoder',
    'JsonDecoder',
    'YamlEncoder',
    'YamlDecoder',
    'DefaultPolicy',
    'DefaultEncoder',
    'DefaultDecoder',
    'DefaultRoot',
    'DefaultFile',
    'DefaultFactory',
]

from functools import partial
from fsfs import factory
from fsfs._compat import callable


class FsFsPolicy(object):
    '''fsfs uses a global policy to specify the behavior of Entry creation,
    data encoding/decoding, and Entry discovery. the default global policy is
    DefaultPolicy which sets the following policy attributes.

    Attributes:
        data_encoder: `YamlEncoder` falls back to `JsonEncoder`
        data_decoder: `YamlDecoder` falls back to `JsonDecoder`
        data_root: '.data'
        data_file: 'data'
        entry_factory: `SimpleEntryFactory`

    Use the following api methods to modify the global policy:
        api.set_data_encoder(data_encoder)
        api.set_data_decoder(data_decoder)
        api.set_data_root(data_root)
        api.set_data_file(data_file)
        api.set_entry_factory(entry_factory)

    You can also subclass FsFsPolicy if you like and use api.set_policy() to
    use an instance of your custom FsFsPolicy.
    '''

    def __init__(
        self,
        data_encoder=None,
        data_decoder=None,
        data_root=None,
        data_file=None,
        entry_factory=None,
        id_generator=None
    ):
        self._data_encoder = data_encoder
        self._data_decoder = data_decoder
        self._data_root = data_root
        self._data_file = data_file
        self._entry_factory = entry_factory
        self._setup_entry_factory(entry_factory)
        self._id_generator = id_generator

    def set_data_encoder(self, data_encoder):
        self._data_encoder = data_encoder

    def get_data_encoder(self):
        return self._data_encoder

    def set_data_decoder(self, data_decoder):
        self._data_decoder = data_decoder

    def get_data_decoder(self):
        return self._data_decoder

    def set_data_root(self, data_root):
        self._data_root = data_root

    def get_data_root(self):
        return self._data_root

    def set_data_file(self, data_file):
        self._data_file = data_file

    def get_data_file(self):
        return self._data_file

    def _setup_entry_factory(self, entry_factory):
        setup_method = getattr(entry_factory, 'setup', None)
        if callable(setup_method):
            setup_method()

    def _teardown_entry_factory(self, entry_factory):
        setup_method = getattr(entry_factory, 'teardown', None)
        if callable(setup_method):
            setup_method()

    def set_entry_factory(self, entry_factory):
        if self._entry_factory and entry_factory is not self._entry_factory:
            self._teardown_entry_factory(self._entry_factory)

        self._entry_factory = entry_factory
        self._setup_entry_factory(entry_factory)

    def get_entry_factory(self):
        return self._entry_factory

    def get_id_generator(self):
        return self._id_generator

    def set_id_generator(self, func):
        self._id_generator = func


# Json Encoder / Decoder
import json
JsonDecoder = json.loads
JsonEncoder = partial(
    json.dumps,
    sort_keys=True,
    indent=4,
    separators=(',', ': ')
)

# Yaml Encoder / Decoder
# Used as Default when pyyaml is available
try:
    import yaml
    YamlDecoder = yaml.safe_load
    YamlEncoder = partial(
        yaml.safe_dump,
        default_flow_style=False
    )
    DefaultDecoder = YamlDecoder
    DefaultEncoder = YamlEncoder
except ImportError:
    YamlEncoder = None
    YamlDecoder = None
    DefaultDecoder = JsonDecoder
    DefaultEncoder = JsonEncoder

# Default ID Generator
import uuid
DefaultIdGenerator = lambda: uuid.uuid4().hex

# Default Data Paths
DefaultRoot = '.data'
DefaultFile = 'data'

# Default Factory
DefaultFactory = factory.SimpleEntryFactory()

# Default Policy
DefaultPolicy = FsFsPolicy(
    data_encoder=DefaultEncoder,
    data_decoder=DefaultDecoder,
    data_root=DefaultRoot,
    data_file=DefaultFile,
    entry_factory=DefaultFactory,
    id_generator=DefaultIdGenerator
)
_global_policy = DefaultPolicy
