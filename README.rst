fsfs
====
Read from and write data to folders on your file system.

----------

Take a peek at how it looks from Python:

.. code-block:: python

    >>> import fsfs
    >>> fsfs.write('tmp/project_dir', start_frame=100, end_frame=200)
    >>> fsfs.read('tmp/project_dir') == {'end_frame': 200, 'start_frame': 100}
    True
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


Testing
=======

.. code-block::

    $ nosetests -v --with-doctest --doctest-extension=.rst


Inspiration
===========
*fsfs* is directly inspired by Abstract Factory's
`openmetadata <https://github.com/abstractfactory/openmetadata>`_. The core
concept of fsfs is the same as openmetadata and the api is similar. However,
fsfs follows a different design pattern allowing you to store data in any
format you like, and does not follow the openmetadata specification. fsfs
comes with encoders for json and yaml out of the box, and allows the storing
of blobs and files.


More Documentation!
===================
`Visit the Full Documentation for an in depth Guide and API Documentation <https://danbradham.github.io/fsfs>`_
