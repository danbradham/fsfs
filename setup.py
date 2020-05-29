# -*- coding: utf-8 -*-
import re
from setuptools import setup, find_packages


def get_info(pyfile):
    '''Retrieve dunder values from a pyfile'''
    info = {}
    info_re = re.compile(r"^__(\w+)__ = ['\"](.*)['\"]")
    with open(pyfile, 'r') as f:
        for line in f.readlines():
            match = info_re.search(line)
            if match:
                info[match.group(1)] = match.group(2)
    return info


info = get_info('./fsfs/__init__.py')


with open('README.rst', 'r') as f:
    long_description = f.read()


setup(
    name=info['title'],
    version=info['version'],
    url=info['url'],
    license=info['license'],
    author=info['author'],
    author_email=info['email'],
    description=info['description'],
    long_description=long_description,
    install_requires=[
        'click',
        'fstrings',
        'scandir',
        'bands'
    ],
    packages=find_packages(),
    package_data={
        '': ['LICENSE', 'README.rst'],
    },
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'fsfs = fsfs.__main__:cli'
        ]
    },
    classifiers=(
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ),
)
