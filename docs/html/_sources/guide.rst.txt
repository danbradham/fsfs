Guide
=====

Tag a folder:

.. code-block:: console

    >>> import fsfs
    >>> fsfs.tag('tmp/my_super_project', 'project')

Get the tags associated with a folder:

.. code-block:: console

    >>> fsfs.get_tags('tmp/my_super_project')
    ['project']

Write some data to your folder:

.. code-block:: console

    >>> fsfs.write('tmp/my_super_project', framerate='24fps')

Read the data back from your folder:

.. code-block:: console

    >>> fsfs.read('tmp/my_super_project')
    {'framerate': '24fps'}

Folders that are tagged or have data stored with them are considered `Entry`'s
by *fsfs* and *fsfs* provides a class by the same name for interacting with
them. Let's take a look at using the `Entry` object.


Getting to know the `Entry` object
----------------------------------

First we will get an `Entry` object representing the folder we tagged project
previously and use it to change our data.

.. code-block:: console

    # Get an Entry object
    >>> entry = fsfs.one('.', 'project')

    # Check some properties and read our data
    >>> entry.name
    'my_super_project'
    >>> entry.path  # doctest: +ELLIPSIS
    '...tmp/my_super_project'
    >>> entry.tags
    ['project']
    >>> entry.read()
    {'framerate': '24fps'}

    # Write some new data
    >>> entry.write(status='active')
    >>> entry.read()
    {'status': 'active', 'framerate': '24fps'}

We used `fsfs.one` to retrieve the first `Entry` tagged `project`. Since we've
tagged one folder with project, we're guaranteed to get an `Entry` for
`tmp/my_super_project`. You could also use `fsfs.search` to get a
generator yielding all `Entry`'s with the tag 'project'.

.. code-block:: console

    >>> for entry in fsfs.search('.', 'project'):
    ...     entry.name
    'my_super_project'


Customizing *fsfs*
------------------

*fsfs* uses the policy pattern to provide a mechanism for customization.
The global policy is used behind the scenes in all api functions and clases.
The policy provides data encoding and decoding, data storage locations, and
a factory used to create `Entry` instances:

+---------------+----------------------------------+---------------------------+
| attribute     | default                          | description               |
+===============+==================================+===========================+
| data_root     | ".data"                          | Name of data subdirectory |
+---------------+----------------------------------+---------------------------+
| data_file     | "data"                           | Name of data file         |
+---------------+----------------------------------+---------------------------+
| data_encoder  | `fsfs.YamlEncoder`               | Encodes data              |
|               | falls back to `fsfs.JsonEncoder` |                           |
+---------------+----------------------------------+---------------------------+
| data_decoder  | `fsfs.YamlDecoder`               | Decodes data              |
|               | falls back to `fsfs.JsonDecoder` |                           |
+---------------+----------------------------------+---------------------------+
| entry_factory | `fsfs.SimpleEntryFactory`        | creates `Entry` objects   |
+---------------+----------------------------------+---------------------------+

Here is how we would modify the global policy's data encoding options.

.. code-block:: console

    >>> fsfs.set_data_encoder(fsfs.JsonEncoder)
    >>> fsfs.set_data_decoder(fsfs.JsonDecoder)
    >>> fsfs.set_data_root('.metadata')
    >>> fsfs.set_data_file('metadata.json')

From now on, when we use *fsfs* data to write data it will be stored in a
subdirectory called `.metadata` in a file called `metadata.json` and encoded
using `JsonEncoder`. The `JsonEncoder` and `JsonDecoder` are simply wrappers
around `json.dumps` and `json.loads`. You can also restore the default global
policy.

.. code-block:: console

    >>> fsfs.set_default_policy()


Advanced: Provide your own `Entry` models
-----------------------------------------

Finally let's take a look at customizing the `Entry` objects returned by the
*fsfs* api. The default policy uses `fsfs.SimpleEntryFactory` which maintains
return instances of the default `Entry` implementation. We can provide our own
`Entry` classes to handle folders with specific tags by creating an instance
of `fsfs.EntryFactory`.

.. code-block:: console

    >>> factory = fsfs.EntryFactory()
    >>> class Project(factory.Entry):
    ...     def special_method(self):
    ...         return 'Hello from your special method!'

    >>> fsfs.set_entry_factory(factory)

By default subclasses are registered to handle a tag that matches the lower
cased class name. You can specify a tag by providing a class attribute
:attr:`type_for_tag`. With our new `EntryFactory` set, the *fsfs* api will use
our `Project` subclass when acting on a folder that is tagged `project`.

.. code-block:: console

    >>> entry = fsfs.one('.', 'project')
    >>> entry.special_method()
    'Hello from your special method!'

An entry factory can be as simple as a function that returns `Entry`
instances. `fsfs.EntryFactory` is a complex callable class that automatically
registers subclasses of the factory's `Entry` base class to handle specific
tags. If we remove the `project` tag from the above example
`Project.special_method` will no longer be available.

.. code-block:: console

    >>> entry.untag('project')
    >>> hasattr(entry, 'special_method')
    False

It seems like our `entry` changed types. The trick here is that
`fsfs.EntryFactory` returns an `EntryProxy` that directs all attribute lookup
to a real `Entry` instance. This allows the entry to magically "*change*"
types when a folder's tags change. Signals are used to keep a cache of
`EntryProxy` and `Entry` objects in sync when tags change, or an entry is moved
on the file system.


Signals
-------

*fsfs* emits the following signals.

+-----------------------+---------------------------+----------------------------------+
| signal                | signature                 | description                      |
+=======================+===========================+==================================+
| fsfs.EntryCreated     | entry                     | When a new Entry is Created      |
+-----------------------+---------------------------+----------------------------------+
| fsfs.EntryMoved       | entry, old_path, new_path | When an Entry is moved           |
+-----------------------+---------------------------+----------------------------------+
| fsfs.EntryTagged      | entry, tags               | When an Entry receives a new tag |
+-----------------------+---------------------------+----------------------------------+
| fsfs.EntryUntagged    | entry, tags               | When an Entry's tag is removed   |
+-----------------------+---------------------------+----------------------------------+
| fsfs.EntryMissing     | entry, exc                | When an Entry goes missing       |
|                       |                           | sent when a relink fails         |
+-----------------------+---------------------------+----------------------------------+
| fsfs.EntryRelinked    | entry, old_path, new_path | When an Entry is relinked        |
+-----------------------+---------------------------+----------------------------------+
| fsfs.EntryDeleted     | entry                     | When an Entry is deleted         |
+-----------------------+---------------------------+----------------------------------+
| fsfs.EntryDataChanged | entry, data               | When an Entry's data is changed  |
+-----------------------+---------------------------+----------------------------------+
| fsfs.EntryDataDeleted | entry                     | When an Entry's data is deleted  |
|                       |                           | sent before EntryDeleted         |
+-----------------------+---------------------------+----------------------------------+
| fsfs.EntryUUIDChanged | entry                     | When an Entry's UUID changes     |
+-----------------------+---------------------------+----------------------------------+

`fsfs.EntryFactory` and `fsfs.SimpleEntryFactory` uses these signals to keep
their caches up-to-date.

Use connect to subscribe a callable to any of the above signals.

.. code-block:: python

    >>> def on_entry_created(entry):
    >>>     print('Entry Created: ', entry)
    >>> fsfs.EntryCreated.connect(lambda entry: print(entry))

For more information on *fsfs* signals visit the API documentation.
