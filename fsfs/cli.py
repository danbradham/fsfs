# -*- coding: utf-8 -*-
from __future__ import print_function
import os
import click
from fstrings import f
import fsfs


def safe_eval(string):
    '''
    Evaluate a string in an empty namespace without __builtins__. Prevents
    imports and dubious scenarious like eval("super") == <type 'super'>.
    '''

    namespace = {'__builtins__': {}}

    try:
        return eval(string, namespace)
    except NameError:
        return eval(repr(string), namespace)
    except:
        raise


@click.group()
def cli():
    '''fsfs command line tools'''


@cli.command()
@click.option('--root', '-r', type=click.Path(), default=os.getcwd())
@click.argument('tags', nargs=-1)
@click.option('--name', '-n')
@click.option('--with-data', '-d', is_flag=True, default=False)
@click.option('--up/--down', 'direction', default=False)
def search(root, tags, name, with_data, direction):
    '''Search for tagged directories'''

    results = fsfs.search(root, tags, direction=int(direction))

    if name:
        results = (e for e in results if name in e.name)

    i = -1
    for i, entry in enumerate(results):
        click.echo(entry)

        if with_data:
            click.echo(fsfs.DATA_ENCODER(entry.read()))


@cli.command()
@click.option('--root', type=click.Path(), default=os.getcwd())
@click.argument('tags', nargs=-1)
@click.option('--name', '-n')
@click.option('--up/--down', 'direction', default=False)
def one(root, tags, name, direction):
    '''Get first search result'''

    results = fsfs.search(root, tags, direction=int(direction))
    if name:
        results = (e for e in results if name in e.name)

    try:
        click.echo(results.next())
    except StopIteration:
        click.echo('0 results found.')


@cli.command()
@click.option('--root', type=click.Path(), default=os.getcwd())
@click.argument('tags', nargs=-1, required=True)
def tag(root, tags):
    '''Tag a directory'''

    fsfs.tag(root, *tags)


@cli.command()
@click.option('--root', type=click.Path(), default=os.getcwd())
@click.argument('tags', nargs=-1, required=True)
def untag(root, tags):
    '''Untag a directory'''

    fsfs.untag(root, *tags)


@cli.command()
@click.option('--root', type=click.Path(), default=os.getcwd())
@click.option('keys', '--key', '-k', multiple=True)
def read(root, keys):
    '''Read metadata'''

    data = fsfs.read(root, *keys)

    click.echo(fsfs.encode_data(data))


@cli.command()
@click.option('--root', type=click.Path(), default=os.getcwd())
@click.option('pairs', '--key', '-k', multiple=True, type=(unicode, unicode))
def write(root, pairs):
    '''Write metadata'''

    data = {}
    for k, v in pairs:
        try:
            data[k] = safe_eval(v)
        except:
            raise click.UsageError(
                'Wrap complex values in quotes: -k key "value"\n'
                '    -k int_key 10\n'
                '    -k float_key 100.0\n'
                '    -k str_key "my_string"\n'
                '    -k dict_key "{\'a\': 10}"\n'
            )

    try:
        fsfs.write(root, **data)
    except Exception as e:
        click.echo('Failed to write data: ')
        click.echo(dict(pairs))
        click.echo(e.message)
    else:
        click.echo(f('Wrote data to {root}'))


@cli.command()
@click.option('--root', type=click.Path(), default=os.getcwd())
@click.option('--remove-root', is_flag=True, default=False)
def delete(root, remove_root):
    '''Delete an entry'''

    entry = fsfs.get_entry(root)
    if not entry.exists:
        raise UsageError(f('{root} is not an Entry.'))

    fsfs.delete(root, remove_root=remove_root)
