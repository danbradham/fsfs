#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function
import __builtin__
import os
import subprocess
import sys
from os.path import join, dirname
from functools import wraps
from fstrings import f
from contextlib import contextmanager
import fsfs
import fire
import fire.helputils
from termcolor import colored
from colorama import init
init()


def usage_string(component, trace=None, verbose=False):
    '''Monkey patch Fire's UsageString function. Hide usage for main cli'''

    if isinstance(component, Tasks):
        # Suppress usage string
        return
    return _usage_string(component, trace, verbose)


_usage_string = fire.helputils.UsageString
fire.helputils.UsageString = usage_string  # Fuck it
_print = __builtin__.print


@contextmanager
def print_prefix(prefix):
    '''Context manager that adds a prefix to all contained print calls.'''

    try:
        old_print = __builtin__.print
        def print(*args, **kwargs):
            _print(prefix, *args, **kwargs)
        __builtin__.print = print
        yield
    finally:
        __builtin__.print = old_print


def log_methods(cls):
    '''Class decorator, logs all method calls using print statements.'''

    def method_wrapper(method):
        @wraps(method)
        def log_method_call(self, *args, **kwargs):
            name = method.__name__
            doc = method.__doc__
            prefix = '[' + name + ']'
            with print_prefix(prefix):
                try:
                    print(colored(doc, 'white'))
                    return_value = method(self, *args, **kwargs)
                except SubprocessError as e:
                    print(colored(e.message, 'red'))
                    if e.stdout:
                        _print(e.stdout)
                    if e.stderr:
                        _print(e.stderr)
                    if cls._verbose:
                        raise
                    sys.exit(e.process.returncode)
                except Exception as e:
                    print(colored(e.message, 'red'))
                    if cls._verbose:
                        raise
                    sys.exit()
                else:
                    print(colored('Success!', 'green'))
                    return return_value
        return log_method_call

    tasks = [
        (k, v) for k, v in cls.__dict__.items()
        if callable(v)
        and not k.startswith('__')
    ]
    for task_name, task_method in tasks:
        setattr(cls, task_name, method_wrapper(task_method))

    return cls


def modify_about(**values):
    '''Modify dunder values of the about file...'''

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


class SubprocessError(Exception):
    '''Custom exception for run, takes an additional Popen argument'''

    def __init__(self, process, stdout, stderr, message):
        self.process = process
        self.stdout = stdout
        self.stderr = stderr
        super(SubprocessError, self).__init__(message)


def run(cmd, **kwargs):
    '''Run a subprocess and wait for it to finish.

    Arguments:
        cmd (str or list): Command to run in subprocess
        **kwargs: kwargs to pass to subprocess.Popen

    Returns:
        Popen

    Raises:
        SubprocessError: with Popen as an attr when subproc fails
    '''

    check_stdout = kwargs.pop('check_stdout', None)
    check_stderr = kwargs.pop('check_stderr', None)

    cmd_kwargs = dict(
        env=os.environ.copy(),
        shell=True,
        universal_newlines=True,
        cwd=os.getcwd(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    cmd_kwargs.update(kwargs)

    process = subprocess.Popen(cmd, **cmd_kwargs)
    out, err = process.communicate()

    process_failed = (
        process.returncode != 0
     or (check_stdout and not check_stdout(out))
     or (check_stderr and not check_stderr(err))
    )

    if process_failed:
        if isinstance(cmd, list):
            msg = 'Subprocess Failed: ' + ' '.join(cmd)
        else:
            msg = 'Subprocess Failed: ' + cmd
        raise SubprocessError(process, out, err, msg)
    return process


def get_tags():
    '''Get a list of git repo tags'''

    p = run('git tag', stdout=subprocess.PIPE)
    tags = [line.rstrip('\n') for line in p.stdout.readlines()]
    p.stdout.close()
    return tags


@log_methods
class Tasks(object):
    '''Package Maintainence tasks

    Tasks:
        test
            Run the test suite
        increment [--major] [--minor] [--patch]
            Increment the package version number
        decrement [--major] [--minor] [--patch]
            Decrement the package version number
        build_docs
            Build the package documentation
        stage
            Stage all changes
        commit [--message]
            Commit all staged changes
        tag [--tag]
            Tag using current version
        push [--remote (origin)] [--branch (master)]
            Push to remote branch
        upload
            Upload to pypi

    Pipelines:

        draft "Commit Message" [--tag] [--remote] [--branch]
            test | stage | commit | tag | push
        publish_docs "Commit Message"
            build_docs | stage | commit | push
        publish "Commit Message" [--tag] [--remote] [--branch] [--where]
            test | stage | commit | tag | push | upload

    '''

    _verbose = False

    def __init__(self):
        vflags = ['-v', '--verbose']
        for f in sys.argv:
            if f in vflags:
                Tasks._verbose = True

    def test(self):
        '''Run Test Suite...'''
        run([
            'nosetests', '-v', '--with-doctest', '--doctest-extension=.rst'
        ])

    def increment(self, major=False, minor=False, patch=True):
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

        modify_about(__version__=version)
        print('changed version to:', version)

    def decrement(self, major=False, minor=False, patch=True):
        '''Decrement package version...'''

        import fsfs
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

        modify_about(__version__=version)
        print('changed version to:', version)

    def build_docs(self):
        '''Build Documentation...'''

        import shutil
        docs = join(dirname(__file__), 'docs')

        print('Removing old docs...')
        if os.path.isdir(join(docs, 'html')):
            shutil.rmtree(join(docs, 'html'))
        if os.path.isdir(join(docs, 'doctrees')):
            shutil.rmtree(join(docs, 'doctrees'))

        print('Building new docs...')
        run('make html', cwd=docs, check_stderr=lambda e: 'Traceback' not in e)

    def stage(self):
        '''Stage changes...'''

        run('git add --all')

    def commit(self, message):
        '''Commit Changes...'''

        run(f('git commit -m "{message}"'))

    def tag(self, tag):
        '''Tag current commit'''

        run('git tag ' + tag)

    def push(self, remote=None, branch=None):
        '''Push commit to remote branch...'''
        remote = remote or 'origin'
        branch = branch or 'master'

        run('git push ' + ' '.join((remote, branch)))

    def upload(self, where=None):
        '''uploading package...not implemented'''
        pass

    def draft(self, message, tag=None, remote=None, branch=None):
        '''Test, Tag, Push Changes...'''

        # Validate
        if tag and tag in get_tags:
            raise Exception('Tag already exists...')

        self.test()
        self.stage()
        self.commit(message)
        if tag:
            self.tag(tag)
        self.push(remote, branch)

    def publish(self, message, tag=None, remote=None, branch=None, where=None):
        '''Test, Tag, Push and Upload Changes...'''

        # Validate
        tag = tag or fsfs.__version__
        if tag in get_tags():
            raise Exception('Tag already exists...')

        self.test()
        self.stage()
        self.commit(message)
        self.tag(tag)
        self.push(remote, branch)
        self.upload(where)

    def publish_docs(self, message, remote=None, branch=None):
        '''Build and Publish Documentation...'''

        self.build_docs()
        self.stage()
        self.commit(message)
        self.push(remote, branch)


if __name__ == '__main__':
    fire.Fire(Tasks)
