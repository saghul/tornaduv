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
    description      = 'Tornado IOLoop implementation with pyuv',
    long_description = open('README.rst', 'r').read(),
    packages         = ['tornaduv'],
    install_requires = [i.strip() for i in open("requirements.txt").readlines() if i.strip()]
)

