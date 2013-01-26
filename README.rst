==============================
A Tornado IOLoop based on pyuv
==============================

tornado-pyuv is a `Tornado <http://www.tornadoweb.org/>`_ IOLoop implementation
which uses `pyuv <http://github.com/saghul/pyuv>`_ as the networking library instead
of the builtin epoll and kqueue pollers included in Tornado.

pyuv is a Python interface for libuv, a high performance asynchronous
networking library used as the platform layer for NodeJS.


Motivation
==========

This is an experimental project to test pyuv's capabilities with a
big framework such as Tornado.


Installation
============

tornado-pyuv requires pyuv (master) and Tornado >= 2.4.0.

::

    pip install git+https://github.com/saghul/pyuv.git
    pip install tornado
    python setup.py install


.. note::
    tornado_pyuv doesn't currently run with Tornado master, use Torndo branch 2.4.


Using it
========

In order to use tornado-pyuv, Tornado needs to be instructed to use
our IOLoop. In order to do that add the following lines at the beginning
of your project, before importing anything from Tornado:

::

    import tornado_pyuv
    tornado_pyuv.install()


Testing
=======

If you want to run the Tornado test suite using tornado_pyuv run the following command:

::

    python -m tornado_pyuv.runtests


Author
======

Saúl Ibarra Corretgé <saghul@gmail.com>


License
=======

tornado-pyuv uses the MIT license, check LICENSE file.

