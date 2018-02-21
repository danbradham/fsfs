# -*- coding: utf-8 -*-
from __future__ import print_function
import itertools
import json
import os
import shutil
import time
from random import choice, randint, sample
from nose.tools import assert_raises, with_setup, make_decorator
from functools import partial, wraps
from tempfile import mkdtemp
from fstrings import f
import string
import fsfs
from fsfs import util


samefile = shutil._samefile
TEMP_DIR = 'tmp'


def provide_tempdir(fn):

    @make_decorator(fn)
    def test_with_tempdir():
        tmpdir = mkdtemp()
        try:
            fn(tmpdir)
        finally:
            shutil.rmtree(tmpdir)

    return test_with_tempdir


def fake_name(used=[]):
    '''Generate a unique 8 character string'''

    while True:
        name = ''.join(
                choice(string.ascii_uppercase + string.digits)
                for _ in range(8)
            )

        if name in used:
            continue

        used.append(name)
        return name


class ProjectFaker():

    projects = [
        'Mean_Streets', 'The_News', 'Ride_By', 'Awful_Stuff', 'Cant_Think',
    ]

    assets = [
        'car', 'bike', 'building', 'hydrant', 'shop', 'street',
        'truck', 'man', 'woman', 'sidewalk', 'table', 'chair', 'bin',
        'mailbox', 'newsstand', 'coffee'
    ]

    variants = [
        'red', 'orange', 'yellow', 'green', 'teal', 'blue', 'violet', 'purple',
        'big', 'small', 'wide', 'tall', 'short', 'extra', 'alt', 'thick',
        'thin', 'rough', 'smooth', 'broken', 'destroyed', 'new', 'fresh',
    ]

    sequences = [
        'chase', 'cross', 'jump', 'fall', 'mug', 'newsy', 'relax', 'find',
    ]

    def __init__(self, root):
        self.root = root

    def project_path(self, root=None, project=None):
        root = root or self.root
        project = project or self.project()
        return f('{root}/{project}')

    def sequence_path(self, root=None, project=None, sequence=None):
        root = root or self.root
        project = project or self.project()
        sequence = sequence or self.sequence()
        return f('{root}/{project}/production/sequences/{sequence}')

    def asset_path(self, root=None, project=None, asset=None):
        root = root or self.root
        project = project or self.project()
        asset = asset or self.asset()
        return f('{root}/{project}/production/assets/{asset}')

    def shot_path(self, root=None, project=None, sequence=None, shot=None):
        root = root or self.root
        project = project or self.project()
        sequence = sequence or self.sequence()
        shot = shot or self.shot()
        return f('{root}/{project}/production/sequences/{sequence}/{shot}')

    def project(self, name=None):
        return name or choice(self.projects)

    def asset(self, name=None):
        return name or choice(self.assets)

    def asset_variant(self, name=None, variant=None):
        name = name or choice(self.assets)
        variant = variant or choice(self.variants)
        return f('{name}_{variant}')

    def sequence(self, name=None, iteration=None):
        name = name or choice(self.sequences)
        iteration = iteration or randint(0, 99)
        return f('seq_{name}_{iteration:0>2d}0')

    def shot(self, iteration=None):
        iteration = iteration or randint(0, 99)
        return f('sh_{iteration:0>2d}0')

    def create(self, name=None, sequences=8, shots=20, assets=20):
        '''This actually uses fsfs to create a project'''

        name = self.project(name)
        path = self.project_path(name)
        fsfs.tag(path, 'project')

        seq_names = []
        for seq_name in sample(self.sequences, sequences):
            seq_name = self.sequence(seq_name)
            seq_names.append(seq_name)
            seq_path = self.sequence_path(project=name, sequence=seq_name)
            fsfs.tag(seq_path, 'sequence')

        for i in range(shots):
            shot_name = self.shot(i)
            shot_path = self.shot_path(
                project=name,
                sequence=seq_name,
                shot=shot_name
            )
            fsfs.tag(shot_path, 'shot')

        perms = [zip(asset, self.variants)
                 for asset in itertools.permutations(
                     self.assets, len(self.variants)
                )]
        variants = [a + '_' + b for (a, b) in itertools.chain(*perms)]
        assets = max([len(assets), len(variants)])
        asset_names = sample(variants, assets)
        for asset_name in asset_names:
            asset_path = self.asset_path(project=name, asset=asset_name)
            fsfs.tag(asset_path, 'asset')


@provide_tempdir
def test_tag(tempdir):
    '''tag and untag'''

    fake = ProjectFaker(root=tempdir)
    asset_path = fake.asset_path()
    tag_path = fsfs.make_tag_path(asset_path, 'asset')

    # fresh tag
    fsfs.tag(asset_path, 'asset')
    assert os.path.isfile(tag_path)

    # tag already exists, should do nothing
    fsfs.tag(asset_path, 'asset')
    assert os.path.isfile(tag_path)

    # remove tag, tag should be gone, data root should still be there
    fsfs.untag(asset_path, 'asset')
    assert not os.path.isfile(tag_path)
    assert os.path.isdir(os.path.join(asset_path, fsfs.get_data_root()))


@provide_tempdir
def test_search_down(tempdir):
    '''search down'''

    fake = ProjectFaker(root=tempdir)
    project = fake.project()
    project_path = fake.project_path(project=project)
    fsfs.tag(project_path, 'project')

    sequence1 = fake.sequence()
    sequence1_path = fake.sequence_path(project=project, sequence=sequence1)
    fsfs.tag(sequence1_path, 'sequence')

    sequence2 = fake.sequence()
    sequence2_path = fake.sequence_path(project=project, sequence=sequence2)
    fsfs.tag(sequence2_path, 'sequence')

    assets = sample(fake.assets, 10)
    hero = assets[0]
    hero_path = fake.asset_path(project=project, asset=hero)
    fsfs.tag(hero_path, 'asset', 'hero')

    for asset in assets[1:]:
        path = fake.asset_path(project=project, asset=asset)
        fsfs.tag(path, 'asset')

    for sequence in (sequence1, sequence2):
        for i in sample(range(99), 10):
            shot = fake.shot(i)
            path = fake.shot_path(
                project=project, sequence=sequence, shot=shot
            )
            fsfs.tag(path, 'shot')

    full_search = fsfs.search(project_path)
    results = list(full_search)
    assert len(results) == 33

    first_result = fsfs.search(project_path).one()
    assert first_result.name == project
    assert samefile(first_result.path, project_path)
    assert 'project' in first_result.tags

    asset_search = fsfs.search(project_path).tags('asset')
    assert len(list(asset_search)) == 10

    hero_search = fsfs.search(project_path).tags('asset', 'hero')
    hero_result = list(hero_search)
    assert len(hero_result) == 1
    assert hero_result[0].name == hero
    assert samefile(hero_result[0].path, hero_path)
    assert ['asset', 'hero'] == hero_result[0].tags


@provide_tempdir
def test_search_up(tempdir):
    '''search up'''

    fake = ProjectFaker(root=tempdir)
    project = fake.project()
    project_path = fake.project_path(project=project)
    fsfs.tag(project_path, 'project')

    sequence = fake.sequence()
    sequence_path = fake.sequence_path(project=project, sequence=sequence)
    fsfs.tag(sequence_path, 'sequence')

    shot = fake.shot()
    shot_path = fake.shot_path(project=project, sequence=sequence, shot=shot)
    fsfs.tag(shot_path, 'shot')

    full_search = fsfs.search(shot_path, direction=fsfs.UP)
    results = list(full_search)
    assert len(results) == 3
    assert results[0].name == shot
    assert results[1].name == sequence
    assert results[2].name == project

    project_result = fsfs.search(shot_path, fsfs.UP).tags('project').one()
    assert project_result.name == project
    assert samefile(project_result.path, project_path)

    no_result = fsfs.search(shot_path, fsfs.UP).tags('unused').one()
    assert no_result is None


@provide_tempdir
def test_read_write(tempdir):
    '''Entry read and write.'''

    fake = ProjectFaker(root=tempdir)
    project_path = fake.project_path()
    fsfs.tag(project_path, 'project')

    # First read will be empty
    project_data = fsfs.read(project_path)
    assert project_data == {}

    # Write updates the cached data and mtime in EntryData
    # This should prevent subsequent reads from unnecessarily accessing disk
    fsfs.write(project_path, hello='world!')
    # ids are the same because we haven't read from disk
    assert fsfs.read(project_path) is project_data
    assert project_data == {'hello': 'world!'}

    # Write another key
    fsfs.write(project_path, integer=10)
    # Still receiving cached data on read
    assert fsfs.read(project_path) is project_data
    assert project_data == {'hello': 'world!', 'integer': 10}

    # If keys are included in read, we return a new dict with only those keys
    assert fsfs.read(project_path, 'integer') is not project_data

    # External data change causes mtime to change
    entry = fsfs.get_entry(project_path)
    time.sleep(0.1)
    with open(entry.data.file, 'w') as f:
        data = dict(hello='wurld!')
        f.write(json.dumps(data))

    # Now ids are different, because our cached mtime is < the mtime on disk
    # causing read to return a new dict
    print(id(fsfs.read(project_path)))
    print(id(project_data))
    assert fsfs.read(project_path) is not project_data


def test_validate_tag():
    '''tag validation'''

    invalid_chars = '!@#$%^&*()+={[}]|\?/><,:;"\'~`'
    for char in invalid_chars:
        assert_raises(fsfs.InvalidTag, fsfs.validate_tag, char)

    valid_names = ['.is-valid', 'is_valid', 'is-valid', 'isvalid']
    for name in valid_names:
        assert fsfs.validate_tag(name)


# Custom EntryFactory with two Registered Types
CustomFactory = fsfs.EntryFactory()


class Project(CustomFactory.Entry):

    def project_method(self):
        pass


class Asset(CustomFactory.Entry):

    def asset_method(self):
        pass


@provide_tempdir
def test_entryfactory(tempdir):
    '''Custom EntryFactory'''

    entry_path = util.unipath(tempdir, 'entry')

    fsfs.set_entry_factory(CustomFactory)
    entry = fsfs.get_entry(entry_path)

    # Factory returns cache entry obj
    assert entry is fsfs.get_entry(entry_path)

    # No tag == default entry
    assert type(entry) == CustomFactory.EntryProxy
    assert type(entry.obj()) == CustomFactory.Entry

    # Add project tag, now we get a Project instance
    entry.tag('project')
    assert type(entry) == CustomFactory.EntryProxy
    assert type(entry.obj()) == CustomFactory.get_type('project')
    assert hasattr(entry, 'project_method')

    # Remove project tag
    entry.untag('project')
    assert type(entry) == CustomFactory.EntryProxy
    assert type(entry.obj()) == CustomFactory.Entry
    assert not hasattr(entry, 'project_method')

    # Add asset tag now we get asset methods
    entry.tag('asset')
    assert type(entry) == CustomFactory.EntryProxy
    assert type(entry.obj()) == CustomFactory.get_type('asset')
    assert hasattr(entry, 'asset_method')

    # Relinked when moved
    new_entry_path = util.unipath(tempdir, 'supercool')
    assert samefile(entry.path, entry_path)
    os.rename(entry.path, new_entry_path)
    entry.read()  # Triggers entry project to relink entry
    assert samefile(entry.path, new_entry_path)

    # Restore DefaultFactory
    fsfs.set_entry_factory(fsfs.DefaultFactory)


def random_entry(entry_path):

    files = [fake_name() for _ in range(4)]
    data_globs = ['/'.join([fsfs.get_data_root(), 'globs', fake_name()])
                  for _ in range(4)]
    data_files = ['/'.join([fsfs.get_data_root(), 'files', fake_name()])
                  for _ in range(4)]
    children = {
        fake_name(): {
            'files': [fake_name() for _ in range(4)],
            'data_globs': [fake_name() for _ in range(4)],
            'data_files': [fake_name() for _ in range(4)],
        }
        for _ in range(4)
    }

    data_manifest = data_globs + data_files
    manifest = files
    for child, data in children.items():
        for f in data['files']:
            manifest.append('/'.join([child, f]))
        for f in data['data_files'] + data['data_globs']:
            data_manifest.append('/'.join([child, fsfs.get_data_root(), f]))

    entry = fsfs.get_entry(entry_path)
    entry.tag('parent')

    for child_entry_path in children:
        child_entry = fsfs.get_entry(
            util.unipath(entry.path, child_entry_path)
        )
        child_entry.tag('child')

    for file in manifest + data_manifest:
        util.touch(util.unipath(entry.path, file))

    return entry, manifest, data_manifest


@provide_tempdir
def test_copy_entry(tempdir):
    '''Copy Entry with files'''

    entry_path = util.unipath(tempdir, 'entry')
    entry_copy_path = util.unipath(tempdir, 'copy')
    entry, manifest, data_manifest = random_entry(entry_path)

    new_entry = entry.copy(entry_copy_path)
    assert new_entry is fsfs.get_entry(entry_copy_path)
    assert new_entry.uuid != entry.uuid

    for file in manifest + data_manifest:
        assert os.path.exists(util.unipath(new_entry.path, file))


@provide_tempdir
def test_copy_entry_only_data(tempdir):
    '''Copy Entry with only_data'''

    entry_path = util.unipath(tempdir, 'entry')
    entry_copy_path = util.unipath(tempdir, 'copy')
    entry, manifest, data_manifest = random_entry(entry_path)

    new_entry = entry.copy(entry_copy_path, only_data=True)
    assert new_entry is fsfs.get_entry(entry_copy_path)
    assert new_entry.uuid != entry.uuid

    for file in manifest:
        assert not os.path.exists(util.unipath(new_entry.path, file))

    for file in data_manifest:
        assert os.path.exists(util.unipath(new_entry.path, file))


@provide_tempdir
def test_move_entry(tempdir):
    '''Move Entry'''

    entry_path = util.unipath(tempdir, 'entry')
    entry_move_path = util.unipath(tempdir, 'move')
    entry, manifest, data_manifest = random_entry(entry_path)
    old_uuid = entry.uuid

    entry.move(entry_move_path)
    assert entry.name == 'move'
    assert entry.path != entry_path
    assert entry.path == entry_move_path
    assert entry is fsfs.get_entry(entry_move_path)
    assert entry.uuid == old_uuid

    for file in manifest + data_manifest:
        assert os.path.exists(util.unipath(entry.path, file))


@provide_tempdir
def test_move_entry_raises(tempdir):
    '''Copy or Move Entry to existing location raises'''

    entry_path = util.unipath(tempdir, 'entry')
    dest_path = util.unipath(tempdir, 'move')
    os.makedirs(dest_path)

    entry = fsfs.get_entry(entry_path)
    entry.tag('generic')
    assert_raises(OSError, entry.move, dest_path)
    assert_raises(OSError, entry.copy, dest_path)
