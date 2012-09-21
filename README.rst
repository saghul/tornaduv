==============================
A Tornado IOLoop based on pyuv
==============================

tornado-pyuv is a Tornado IOLoop implementation which uses pyuv
as the networking library instead of the builtin epoll and kqueue
pollers included in Tornado.

pyuv is a Python interface for libuv, a high performance asynchronous
networking library used as the platform layer for NodeJS.

Source code is on `GitHub <http://github.com/saghul/pyuv>`_.


Motivation
==========

This is an experimental project to test pyuv's capabilities with a
big framework such as Tornado.


Installation
============

tornado_pyuv requires pyuv >= 0.9.0 and Tornado > 2.4.0, so right now the
only way to get those is by installing them straight from GitHub:

::

    pip install git+https://github.com/saghul/pyuv.git
    pip install git+https://github.com/facebook/tornado.git


Using it
========

In order to use tornado-pyuv, Tornado needs to be instructed to use
our IOLoop. In order to do that add the following lines at the beginning
of your project, before importing anything from Tornado:

::

    import tornado_pyuv
    tornado_pyuv.install()


Author
======

Saúl Ibarra Corretgé <saghul@gmail.com>


License
=======

tornado-pyuv uses the MIT license, check LICENSE file.

