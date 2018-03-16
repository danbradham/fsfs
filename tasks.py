#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
from invoke import task, Failure, run
from os.path import join, dirname, isdir
import fsfs
import shutil


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
def increment(major=False, minor=False, patch=True):
    '''Increment package version'''

    import fsfs
    cmajor, cminor, cpatch = fsfs.__version__.split('.')

    if major:
        major = str(int(cmajor) + 1)
        version = major + '.0.0'
    elif minor:
        minor = str(int(cminor) + 1)
        version = cmajor + '.' + minor + '.0'
    else:
        patch = str(int(cpatch) + 1)
        version = cmajor + '.' + cminor + '.' + patch

    print('Incrementing package version by {}'.format(version))
    modify_about(__version__=version)
    print('Changed version to:', version)


@task
def decrement(major=False, minor=False, patch=True):
    '''Decrement package version...'''

    cmajor, cminor, cpatch = fsfs.__version__.split('.')

    if major:
        major = str(int(cmajor) - 1)
        version = major + '.0.0'
    elif minor:
        minor = str(int(cminor) - 1)
        version = cmajor + '.' + minor + '.0'
    else:
        patch = str(int(cpatch) - 1)
        version = cmajor + '.' + cminor + '.' + patch

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


@task
def tag(ctx, tag=None):
    '''Tag current commit'''

    tag = tag or fsfs.__version__
    if tag in get_tags():
        raise Failure('Tag already exists...')

    ctx.run('git tag ' + tag)


@task
def push(ctx, remote=None, branch=None):
    '''Push commit to remote branch...'''
    remote = remote or 'origin'
    branch = branch or 'master'

    ctx.run('git push --tags {} {}'.format(remote, branch))


@task
def tests(ctx):
    '''Run test suite'''

    docs = join(dirname(__file__), 'docs')
    ctx.run('nosetests -v --with-doctest --doctest-extension=rst')
    with ctx.cd(docs):
        ctx.run('nosetests -v --with-doctest --doctest-extension=rst')


@task
def upload(ctx, where=None):
    '''uploading package...not implemented'''
    pass


@task
def draft(ctx, tag=None, remote=None, branch=None):
    '''Test, Tag, Push Changes...'''

    tests(ctx)
    if tag:
        tag(ctx, tag)
    push(ctx, remote, branch)


@task
def publish(ctx, tag=None, remote=None, branch=None, where=None):
    '''Test, Tag, Push and Upload Changes...'''

    tests(ctx)
    tag(ctx, tag)
    push(ctx, remote, branch)
    upload(ctx, where)
