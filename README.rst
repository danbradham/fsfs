fsfs
====
Tag and store metadata on your filesystem.


How it looks
============

Command line::

    > fsfs tag project --root=tmp/project_dir
    > fsfs search project
    .../tmp/project_dir
    > fsfs write -k start_frame 100 -k end_frame 200 --root=tmp/project_dir
    > fsfs read --root=tmp/project_dir
    {
        'start_frame': 100,
        'end_frame': 200
    }

Python::

    >>> import fsfs
    >>> fsfs.tag('tmp/project_dir', 'project')
    >>> fsfs.search('.', 'project')
    .../tmp/project_dir
    >>> fsfs.write('tmp/project_dir', start_frame=100, end_frame=100)
    >>> fsfs.read('tmp/project_dir')
    {
        'start_frame': 100,
        'end_frame': 200
    }
