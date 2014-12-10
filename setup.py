# -*- coding: utf-8 -*-

import re
from distutils.core import setup


def get_version():
    return re.search(r"""__version__\s+=\s+(?P<quote>['"])(?P<version>.+?)(?P=quote)""", open('tornaduv/__init__.py').read()).group('version')

setup(
    name             = 'tornaduv',
    version          = get_version(),
    url              = 'https://github.com/saghul/tornaduv',
    author           = 'Saúl Ibarra Corretgé',
    author_email     = 'saghul@gmail.com',
    license          = 'MIT License',
    description      = 'Tornado IOLoop implementation with pyuv',
    long_description = open('README.rst', 'r').read(),
    packages         = ['tornaduv'],
    install_requires = [i.strip() for i in open("requirements.txt").readlines() if i.strip()],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4'
        ]
)
