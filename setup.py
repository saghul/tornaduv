# -*- coding: utf-8 -*-

import re
from distutils.core import setup


def get_version():
    return re.search(r"""__version__\s+=\s+(?P<quote>['"])(?P<version>.+?)(?P=quote)""", open('tornado_pyuv/__init__.py').read()).group('version')

setup(
    name             = 'tornado-pyuv',
    version          = get_version(),
    url              = 'https://github.com/saghul/tornado-pyuv',
    author           = 'Saúl Ibarra Corretgé',
    author_email     = 'saghul@gmail.com',
    description      = 'Tornado IOLoop implementation with pyuv',
    long_description = open('README.rst', 'r').read(),
    packages         = ['tornado_pyuv'],
    install_requires = [i.strip() for i in open("requirements.txt").readlines() if i.strip()]
)

