#!/usr/bin/env python

from distutils.core import setup
from distutils.extension import Extension
from Cython.Build import cythonize
import sys

compiler_directives = {}
if '--enable-profiling' in sys.argv:
     compiler_directives['profile'] = True
     sys.argv.remove('--enable-profiling')

extensions = [
    Extension('pywr_extras._hydrology', ['pywr_extras/_hydrology.pyx']),
]

setup(
    name='pywr-extras',
    version='0.1',
    description='Useful utilities for Pywr',
    author='James Tomlinson',
    author_email='tomo.bbe@gmail.com',
    packages=['pywr_extras'],
    ext_modules=cythonize(extensions, compiler_directives=compiler_directives)
)
