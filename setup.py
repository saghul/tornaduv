# -*- coding: utf-8 -*-

from setuptools import setup
from tornado_pyuv import __version__


setup(
    name             = 'tornado-pyuv',
    version          = __version__,
    url              = 'https://github.com/saghul/tornado-pyuv',
    author           = 'Saúl Ibarra Corretgé',
    author_email     = 'saghul@gmail.com',
    description      = 'Tornado IOLoop implementation with pyuv',
    long_description = open('README.rst', 'r').read(),
    packages         = ['tornado_pyuv']
)

