#!/usr/bin/env python

# Copyright (c) 2008 Valentino Volonghi.
# See LICENSE for details.

"""
Distutils installer for AMPoule.
"""

try:
    # Load setuptools, to build a specific source package
    import setuptools
except ImportError:
    pass

import sys, os
import ampoule

install_requires = ["Twisted>=8.0.1"]

setup = setuptools.setup
find_packages = setuptools.find_packages

description = """A process pool implementation in Twisted Matrix and AMP"""

long_description = file('README').read()

setup(
    name = "ampoule",
    author = "Valentino Volonghi",
    author_email = "dialtone@gmail.com",
    description = description,
    long_description = long_description,
    license = "MIT License",
    version=ampoule.__version__,
    install_requires=install_requires,
    url="https://launchpad.net/ampoule",
    classifiers = [
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Topic :: System',
    ],
    packages=find_packages(exclude=['ez_setup', 'examples']),
    include_package_data = True,
    zip_safe=False
)
