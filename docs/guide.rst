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

Let's get an `Entry` object representing the folder we created previously and
use it to change our data.

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
only created one folder tagged `project`, we're guaranteed to get an `Entry`
for `tmp/my_super_project`. You could also use `fsfs.search` to get a
generator yielding all `Entry`'s with the tag 'project' like so:

.. code-block:: console

    >>> for entry in fsfs.search('.', 'project'):
    ...     entry.name
    'my_super_project'


Customizing *fsfs*
------------------

*fsfs* uses the policy pattern to provide a mechanism for customizing *fsfs*.
The global policy is used behind the scenes in all api functions and clases.
The policy provides data encoding and decoding, data storage locations, and
a factory used to create `Entry` instances:

- data_encoder: a function or callable class that encodes data

    - defaults to `fsfs.YamlEncoder` falls back to `fsfs.JsonEncoder`

- data_decoder: a function or callable class that decodes data

    - defaults to `fsfs.YamlDecoder` falls back to `fsfs.JsonDecoder`

- data_root: the name of the subdirectory to store data in

    - defaults to ".data"

- data_file: the name of the file to store encoded data

    - defaults to "data"

- entry_factory: a function or callabled class used by `fsfs.get_entry` to
  retrieve an `Entry` object for the given path

    - defaults to `fsfs.SimpleEntryFactory` which simple yields the base
      implementation `Entry` for every path


Let's take a look at modifying the default policy's data storage behavior:

.. code-block:: console

    >>> fsfs.set_data_encoder(fsfs.JsonEncoder)
    >>> fsfs.set_data_decoder(fsfs.JsonDecoder)
    >>> fsfs.set_data_root('.metadata')
    >>> fsfs.set_data_file('metadata.json')

Now when we use *fsfs* data to write data it will be stored in a subdirectory
of the folder called `.metadata` in a file called `metadata.json` and encoded
using `JsonEncoder`. The `JsonEncoder` and `JsonDecoder` are just wrappers
around `json.dumps` and `json.loads`.


Advanced: Provide your own `Entry` models
-----------------------------------------

Finally let's take a look at customing the `Entry` objects returned by the
*fsfs* api. By changing the global policy's `EntryFactory` we can customize the `Entry`. First let's reset our policy to the defaults.

.. code-block:: console

    >>> fsfs.set_default_policy()

OK! Now let's create a new `EntryFactory` instance that will allow us to
define `Entry` models to handle folders tagged with specific tags.

.. code-block:: console

    >>> factory = fsfs.EntryFactory()
    >>> class Project(factory.Entry):
    ...     def special_method(self):
    ...         return 'Hello from your special method!'

    >>> fsfs.set_entry_factory(factory)

Great. When we use *fsfs* now, and we get an `Entry` for a folder tagged
`project` we will receive an instance of our `Project` class instead of the
default `Entry`.

.. code-block:: console

    >>> entry = fsfs.one('.', 'project')
    >>> entry.special_method()
    'Hello from your special method!'

A couple notes about entry factories. An entry factory can be as simple as a
function that returns and `Entry` instance. `fsfs.EntryFactory` is a complex
class that automatically registers subclasses of the factory's Entry base class
to handle specific tags. Instead of directly handing `Entry` classes back to
the user, `fsfs.EntryFactory` returns an `EntryProxy` instance that wraps a
cached `Entry` instance. This allows the proxy to magically "change" types
when a folders tags change. If you remove the `project` tag from the above
example `Project.special_method` will no longer be available.

.. code-block:: console

    >>> entry.untag('project')
    >>> hasattr(entry, 'special_method')
    False

To get the actual object the proxy is currently referencing you can call the
proxy's obj method.

.. code-block:: console

    >>> entry.tag('project')
    >>> assert type(entry.obj()) is Project
