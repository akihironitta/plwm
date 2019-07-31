#!/usr/bin/env python

from distutils.core import setup
import sys

if sys.version < '2.3.3':
    from distutils.dist import DistributionMetadata
    DistributionMetadata.classifiers = None
    DistributionMetadata.download_url = None

import plwm

setup(name='PLWM',
        version=plwm.__version__,

        description='Modularized X window manager for keyboard-loving programmers',
        download_url='http://sourceforge.net/projects/plwm/files/',
        url='http://plwm.sourceforge.net/',
        license='GPL',

        maintainer='Mike Meyer',
        maintainer_email='mwm@mired.org',
        author='Peter Liljenberg',
        author_email='petli@ctrl-c.liu.se',

        packages=['plwm'],

        classifiers=[
            'Development Status :: 5 - Production/Stable',
            'Environment :: X11 Applications',
            'Intended Audience :: Developers',
            'Intended Audience :: End Users/Desktop',
            'License :: OSI Approved :: GNU General Public License (GPL)',
            'Natural Language :: English',
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Topic :: Desktop Environment :: Window Managers',
            'Topic :: Software Development :: Libraries',
            'Topic :: Software Development :: Libraries :: Python Modules',
            'Topic :: Software Development :: User Interfaces'
            ],
        )



