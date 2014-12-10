==============================
A Tornado IOLoop based on pyuv
==============================

.. image:: https://travis-ci.org/saghul/tornaduv.svg?branch=master
   :target: https://travis-ci.org/saghul/tornaduv
   :alt: Build status

.. image:: https://pypip.in/download/tornaduv/badge.png
    :target: https://pypi.python.org/pypi/tornaduv/
    :alt: Downloads

.. image:: https://pypip.in/version/tornaduv/badge.png
    :target: https://pypi.python.org/pypi/tornaduv/
    :alt: Latest Version

.. image:: https://pypip.in/license/tornaduv/badge.png
    :target: https://pypi.python.org/pypi/tornaduv/
    :alt: License


tornaduv is a `Tornado <http://www.tornadoweb.org/>`_ IOLoop implementation
which uses `pyuv <http://github.com/saghul/pyuv>`_ as the networking library instead
of the builtin epoll and kqueue pollers included in Tornado.

pyuv is a Python interface for libuv, a high performance asynchronous
networking library used as the platform layer for NodeJS.


Installation
============

tornaduv requires pyuv >= 1.0.0 and Tornado >= 3.0.

::

    pip install tornaduv


Using it
========

In order to use tornaduv, Tornado needs to be instructed to use
our IOLoop. In order to do that add the following lines at the beginning
of your project:

::

    from tornado.ioloop import IOLoop
    from tornaduv import UVLoop
    IOLoop.configure(UVLoop)


Testing
=======

If you want to run the Tornado test suite using tornaduv run the following command:

::

    python -m tornado.test.runtests --ioloop='tornaduv.UVLoop' --verbose


Authors
=======

Saúl Ibarra Corretgé <saghul@gmail.com>
Marc Schlaich <marc.schlaich@gmail.com>


License
=======

tornaduv uses the MIT license, check LICENSE file.

