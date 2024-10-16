#!/usr/bin/env python
# -*- test-case-name: ampoule -*-

# Copyright (c) 2008 Valentino Volonghi.
# See LICENSE for details.

"""
Distutils/Setuptools installer for AMPoule.
"""

from setuptools import setup

install_requires = ["Twisted[tls]>=17"]

description = """A process pool built on Twisted and AMP."""
long_description = open('README.md').read()

setup(
    name = "ampoule",
    author = "Valentino Volonghi",
    author_email = "dialtone@gmail.com",
    maintainer = "Glyph Lefkowitz",
    maintainer_email = "glyph@twistedmatrix.com",
    description = description,
    description_content_type='text/markdown',
    long_description = long_description,
    long_description_content_type='text/markdown',
    license = "MIT License",
    python_requires=">=3",
    install_requires=install_requires + ['incremental'],
    url="https://github.com/twisted/ampoule",
    classifiers = [
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Topic :: System',
    ],
    packages=["ampoule", "ampoule.test"],
    package_data={'twisted': ['plugins/ampoule_plugin.py']},
    use_incremental=True,
    setup_requires=['incremental'],
    include_package_data = True,
    zip_safe=False
)
