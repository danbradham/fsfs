fsfs
====
Read from and write data to folders on your file system.

----------

Take a peek at how it looks from Python:

.. code-block:: python

    >>> import fsfs
    >>> fsfs.write('tmp/project_dir', start_frame=100, end_frame=100)
    >>> fsfs.read('tmp/project_dir')
    {
        'start_frame': 100,
        'end_frame': 200
    }
    >>> import shutil; shutil.rmtree('tmp')

and from the command line:

.. code-block::

    $ mkdir tmp/project_dir
    $ cd tmp/project_dir
    $ fsfs write -k start_frame 100 -k end_frame 200
    $ fsfs read
    {
        'start_frame': 100,
        'end_frame': 200
    }


Features
========

- Read from and write data to folders

    - pluggable data encoding with default implementations for json and yaml
    - supports blobs and files

- Tag and Untag folders allowing quick lookup

- Folders wrapped in `Entry` objects allows ORM-like patterns
- Uses a factory to create `Entry` objects
- Generates UUIDs for each folder you touch with *fsfs*

    - Allows *fsfs* to react to file system changes outside your program
    - Allows *fsfs* to relink `Entry` models


Why use *fsfs* instead of a database
====================================

Certain types of creative projects rely heavily on binary files output from
content creation software and close management of the file system they reside
in. In these cases maintaining a separate database to track your files and
locations can be tedious and can easily become out of sync.

This is exactly the problem *fsfs* is designed to address. *fsfs* stores your
data alongside your files, so when your files are reorganized their associated
data comes along for the ride.


Installation
============

.. code-block::

    $ pip install git+git://github.com/danbradham/fsfs.git


Guide
=====

Tag a folder:

.. code-block::

    >>> import fsfs
    >>> fsfs.tag('tmp/my_super_project', 'project')

Get the tags associated with a folder:

.. code-block::

    >>> fsfs.get_tags('tmp/my_super_project')
    ['project']

Write some data to your folder:

.. code-block::

    >>> fsfs.write('tmp/my_super_project', framerate='24fps')

Read the data back from your folder:

.. code-block::

    >>> fsfs.read('tmp/my_super_project')
    '24fps'

Folders that are tagged or have data stored with them are considered `Entry`'s
by *fsfs* and *fsfs* provides a class by the same name for interacting with
them. Let's take a look at using the `Entry` object.


Getting to know the `Entry` object
--------------------------------

Let's get an `Entry` object representing the folder we created previously and
use it to change our data.

.. code-block::

    # Get an Entry object
    >>> entry = fsfs.one('project')

    # Check some properties and read our data
    >>> entry.name
    'my_super_project'
    >>> entry.path
    'tmp/my_super_project'
    >>> entry.tags
    ['project']
    >>> entry.read()
    {'framerate': '24fps'}

    # Write some new data
    >>> entry.write(status='active')
    >>> entry.read()
    {'framerate': '24fps', 'status':'active'}

We used `fsfs.one` to retrieve the first `Entry` tagged `project`. Since we've
only created one folder tagged `project`, we're guaranteed to get an `Entry`
for `tmp/my_super_project`. You could also use `fsfs.search` to get a
generator yielding all `Entry`'s with the tag 'project' like so:

.. code-block::

    >>> for entry in fsfs.search('project'):
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

.. code-block::

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

.. code-block::

    >>> fsfs.set_default_policy()

OK! Now let's create a new `EntryFactory` instance that will allow us to
define `Entry` models to handle folders tagged with specific tags.

.. code-block::

    # Create our new factory
    >>> factory = fsfs.EntryFactory()
    >>> class Project(factory.Entry):
    ...     def special_method(self):
    ...         return 'Hello from your special method!'

    # Set the global policy's entry_factory to our new factory
    >>> fsfs.set_entry_factory(factory)

Great. When we use *fsfs* now, and we get an `Entry` for a folder tagged
`project` we will receive an instance of our `Project` class instead of the
default `Entry`.

.. code-block::

    >>> entry = fsfs.one('project')
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

.. code-block::

    >>> entry.untag('project')
    >>> hasattr(entry, 'special_method')
    False

To get the actual object the proxy is currently referencing you can call the
proxy's obj method.

.. code-block::

    >>> entry.tag(entry, 'project')
    >>> assert type(entry.obj()) is Project


Inspiration
===========
*fsfs* is directly inspired by Abstract Factory's
`openmetadata <https://github.com/abstractfactory/openmetadata>`_. The core
concept of fsfs is the same as openmetadata and the api is similar. However,
fsfs follows a different design pattern allowing you to store data in any
format you like, and does not follow the openmetadata specification. fsfs
comes with encoders for json and yaml out of the box, and allows the storing
of blobs and files.
