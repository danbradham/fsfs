#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
from invoke import task, Failure, run
from os.path import join, dirname, isdir, exists
import fsfs
import sys
import shutil


VER = sys.version_info
PY37 = (VER.major, VER.minor) == (3, 7)


def modify_about(**values):
    '''Modify dunder values in file...'''

    about = join(dirname(__file__), 'fsfs', '__init__.py')

    with open(about, 'r') as file:
        about_lines = file.readlines()

    for i, line in enumerate(about_lines):
        if line.startswith('__'):
            dunder = line.split(' = ')[0]
            if dunder in values:
                about_lines[i] = dunder + ' = ' + repr(values[dunder]) + '\n'

    with open(about, 'w') as file:
        file.writelines(about_lines)


def get_tags():
    '''Get a list of git repo tags'''

    result = run('git tag')
    tags = result.stdout.split('\n')
    return tags


@task
def increment(ctx, major=False, minor=False, patch=True):
    '''Increment package version'''

    import fsfs
    cmajor, cminor, cpatch = fsfs.__version__.split('.')

    version = '{}.{}.{}'
    if major:
        version = version.format(int(cmajor) + 1, 0, 0)
    elif minor:
        version = version.format(cmajor, int(cminor) + 1, 0)
    else:
        version = version.format(cmajor, cminor, int(cpatch) + 1)

    print('Incrementing package version by {}'.format(version))
    modify_about(__version__=version)
    print('Changed version to:', version)


@task
def decrement(ctx, major=False, minor=False, patch=True):
    '''Decrement package version...'''

    cmajor, cminor, cpatch = fsfs.__version__.split('.')

    version = '{}.{}.{}'
    if major:
        version = version.format(int(cmajor) - 1, 0, 0)
    elif minor:
        version = version.format(cmajor, int(cminor) - 1, 0)
    else:
        version = version.format(cmajor, cminor, int(cpatch) - 1)

    print('Decrementing package version by {}'.format(version))
    modify_about(__version__=version)
    print('Changed version to:', version)


@task
def build_docs(ctx):
    '''Build Documentation...'''

    docs = join(dirname(__file__), 'docs')

    print('Removing old docs...')
    if isdir(join(docs, 'html')):
        shutil.rmtree(join(docs, 'html'))
    if isdir(join(docs, 'doctrees')):
        shutil.rmtree(join(docs, 'doctrees'))

    print('Building new docs...')
    with ctx.cd(docs):
        result = ctx.run('make html')
        if 'Traceback' in result.stdout + result.stderr:
            raise Failure(result, 'Failed to build docs...')


@task
def stage(ctx):
    '''Stage changes...'''
    ctx.run('git add --all')
    print('Staged Changes...')


@task
def commit(ctx, message):
    '''Commit Changes...'''

    ctx.run('git commit -m {!r}'.format(message))


@task('tag')
def _tag(ctx, tag=None):
    '''Tag current commit'''

    tag = tag or fsfs.__version__
    if tag in get_tags():
        print('Overwriting tag', tag)

    ctx.run('git tag --force ' + tag)


@task
def push(ctx, remote=None, branch=None):
    '''Push commit to remote branch...'''
    remote = remote or 'origin'
    branch = branch or 'master'

    ctx.run('git push {} {}'.format(remote, branch))
    ctx.run('git push --force --tags {} {}'.format(remote, branch))


@task
def tests(ctx):
    '''Run test suite'''

    ctx.run('nosetests -v')


@task
def build(ctx):
    '''Run python setup.py sdist bdist_wheel'''

    cleanup(ctx)
    ctx.run('python setup.py sdist bdist_wheel')


@task
def cleanup(ctx):
    '''Remove build and dist directories'''
    if exists('build'):
        shutil.rmtree('build')
    if exists('dist'):
        shutil.rmtree('dist')


@task
def upload(ctx, where=None):
    '''uploading package'''

    ctx.run('twine upload dist/*')


@task
def draft(ctx, tag=None, remote=None, branch=None):
    '''Test, Tag, Push Changes...'''

    tests(ctx)
    if tag:
        _tag(ctx, tag)
    push(ctx, remote, branch)


@task
def publish(ctx, tag=None, remote=None, branch=None, where=None):
    '''Test, Tag, Push and Upload Changes...'''

    tests(ctx)
    if tag:
        _tag(ctx, tag)
    push(ctx, remote, branch)

    try:
        build(ctx)
        upload(ctx, where)
    finally:
        cleanup(ctx)
