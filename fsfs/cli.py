# -*- coding: utf-8 -*-
from __future__ import print_function
import os
import sys
import ast
import click
from click import group, argument, option
from fstrings import f
import fsfs


class NameToString(ast.NodeTransformer):

    def visit_Name(self, node):
        if node.id in ('True', 'False', 'None'):
            return node
        return ast.copy_location(ast.Str(node.id), node)


def safe_eval(string):
    tree = NameToString().visit(ast.parse(string, mode='eval'))
    value = ast.literal_eval(tree)
    return value


class ObjType(click.ParamType):
    '''The ObjType converts a command line argument to a python object. Using
    ast.literal_eval to safely evaluate the string argument. This is the same
    technique used by Python Fire to evaluate arguments.'''

    name = 'object'

    def convert(self, value, param, ctx):
        try:
            value = safe_eval(value)
        except:
            self.fail('%s is not a valid python object' % value, param, ctx)
        else:
            return value


OBJECT = ObjType()


class ListOption(click.Option):

    def add_to_parser(self, parser, ctx):
        result = super(ListOption, self).add_to_parser(parser, ctx)

        name = self.opts[0]
        self._parser = parser._long_opt.get(name, parser._short_opt.get(name))
        self._process = self._parser.process

        def process(value, state):
            value = [safe_eval(value)]
            while state.rargs:
                next_value = state.rargs[0]
                for prefix in self._parser.prefixes:
                    if next_value.startswith(prefix):
                        break
                else:
                    state.rargs.pop(0)
                    value.append(safe_eval(next_value))

            return self._process(value, state)

        self._parser.process = process
        return result


@group()
def cli():
    '''fsfs command line tools'''


@cli.command()
@option('--root', '-r', default=os.getcwd(), help='Root directory of search')
@option('--up/--down', 'direction', default=False, help='Direction to search')
@argument('name', required=False, help='Like "entry" or "parent/entry"')
@option('--tags', '-t', cls=ListOption, help='List of tags to match')
def search(root, direction, name, tags):
    '''Search for Entries'''

    entries = fsfs.search(root, direction=int(direction))

    if name:
        entries = entries.name(name)

    if tags:
        entries = entries.tags(*tags)

    num_entries = 0
    for entry in entries:
        num_entries += 1
        print(entry)

    if not num_entries:
        print('No entries found')
        sys.exit(1)


@cli.command()
@option('--root', '-r', default=os.getcwd(), help='Root directory of search')
@option('--up/--down', 'direction', default=False, help='Direction to search')
@argument('name', required=False, help='Like "entry" or "parent/entry"')
@option('--tags', '-t', cls=ListOption, help='List of tags to match')
def one(root, direction, name, tags):
    '''Get first search result'''

    entries = fsfs.search(root, direction=int(direction))

    if name:
        entries = entries.name(name)

    if tags:
        entries = entries.tags(*tags)

    entry = entries.one()

    if entry:
        print(entry)
    else:
        print('No entries found')
        sys.exit(1)

@cli.command()
@option('--root', '-r', default=os.getcwd())
@argument('tags', nargs=-1, required=True)
def tag(root, tags):
    '''Tag a directory'''

    fsfs.tag(root, *tags)


@cli.command()
@option('--root', '-r', default=os.getcwd())
@argument('tags', nargs=-1, required=True)
def untag(root, tags):
    '''Untag a directory'''

    fsfs.untag(root, *tags)


@cli.command()
@option('--root', '-r', default=os.getcwd())
@argument('keys', nargs=-1)
def read(root, keys):
    '''Read metadata'''

    data = fsfs.read(root, *keys)

    print(fsfs.encode_data(data))


@cli.command()
@option('--root', '-r', default=os.getcwd())
@option('data', '--key', '-k', multiple=True, type=(unicode, OBJECT))
def write(root, data):
    '''Write metadata'''

    data = {k: v for k, v in data}

    try:
        fsfs.write(root, **data)
    except Exception as e:
        print('Failed to write data: ')
        print(dict(pairs))
        print(e.message)
    else:
        print(f('Wrote data to {root}'))


@cli.command()
@option('--root', '-r', default=os.getcwd())
@option('--remove-root', is_flag=True, default=False)
def delete(root, remove_root):
    '''Delete an entry'''

    entry = fsfs.get_entry(root)
    if not entry.exists:
        raise UsageError(f('{root} is not an Entry.'))

    fsfs.delete(root, remove_root=remove_root)
