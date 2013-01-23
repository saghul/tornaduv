# -*- coding: utf-8 -*-

from setuptools import setup

setup(
    name             = 'tornado-pyuv',
    version          = '0.2.1',
    url              = 'https://github.com/saghul/tornado-pyuv',
    author           = 'Saúl Ibarra Corretgé',
    author_email     = 'saghul@gmail.com',
    description      = 'Tornado IOLoop implementation with pyuv',
    long_description = open('README.rst', 'r').read(),
    packages         = ['tornado_pyuv']
)

