==============================
A Tornado IOLoop based on pyuv
==============================

tornado-pyuv is a `Tornado <http://www.tornadoweb.org/>`_ IOLoop implementation
which uses `pyuv <http://github.com/saghul/pyuv>`_ as the networking library instead
of the builtin epoll and kqueue pollers included in Tornado.

pyuv is a Python interface for libuv, a high performance asynchronous
networking library used as the platform layer for NodeJS.


Installation
============

tornado-pyuv requires pyuv >= 0.10.0 and Tornado (master).

::

    pip install -U pyuv
    pip install git+https://github.com/facebook/tornado.git
    git clone https://github.com/saghul/tornado-pyuv.git
    cd tornado-pyuv
    python setup.py install


Using it
========

In order to use tornado-pyuv, Tornado needs to be instructed to use
our IOLoop. In order to do that add the following lines at the beginning
of your project:

::

    from tornado.ioloop import IOLoop
    from tornado_pyuv import UVLoop
    IOLoop.configure(UVLoop)


Testing
=======

If you want to run the Tornado test suite using tornado_pyuv run the following command:

::

    python -m tornado.test.runtests --ioloop='tornado_pyuv.UVLoop' --verbose


Author
======

Saúl Ibarra Corretgé <saghul@gmail.com>


License
=======

tornado-pyuv uses the MIT license, check LICENSE file.

