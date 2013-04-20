# -*- coding: utf-8 -*-

from distutils.core import setup


setup(
    name             = 'tornado-pyuv',
    version          = '0.3.0',
    url              = 'https://github.com/saghul/tornado-pyuv',
    author           = 'Saúl Ibarra Corretgé',
    author_email     = 'saghul@gmail.com',
    description      = 'Tornado IOLoop implementation with pyuv',
    long_description = open('README.rst', 'r').read(),
    packages         = ['tornado_pyuv'],
    install_requires = [i.strip() for i in open("requirements.txt").readlines() if i.strip()]
)

