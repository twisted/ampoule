#!/usr/bin/env python

# Copyright (c) 2008 Valentino Volonghi.
# See LICENSE for details.

"""
Distutils/Setuptools installer for AMPoule.
"""

try:
    # Load setuptools, to build a specific source package
    from setuptools import setup
except ImportError:
    from distutils.core import setup

try:
    import ampoule
    version = ampoule.__version__
except ImportError:
    version = "0.2.0"

install_requires = ["Twisted>=8.0.1", "pyOpenSSL"]

description = """A process pool implementation in Twisted Matrix and AMP"""
long_description = file('README').read()

setup(
    name = "ampoule",
    author = "Valentino Volonghi",
    author_email = "dialtone@gmail.com",
    description = description,
    long_description = long_description,
    license = "MIT License",
    version=version,
    install_requires=install_requires,
    url="https://launchpad.net/ampoule",
    classifiers = [
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Topic :: System',
    ],
    packages=["ampoule", "ampoule.test", "twisted"],
    package_data={'twisted': ['plugins/ampoule_plugin.py']},
    include_package_data = True,
    zip_safe=False
)
