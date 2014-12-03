==============================
A Tornado IOLoop based on pyuv
==============================

tornaduv is a `Tornado <http://www.tornadoweb.org/>`_ IOLoop implementation
which uses `pyuv <http://github.com/saghul/pyuv>`_ as the networking library instead
of the builtin epoll and kqueue pollers included in Tornado.

pyuv is a Python interface for libuv, a high performance asynchronous
networking library used as the platform layer for NodeJS.


Installation
============

tornaduv requires pyuv >= 0.10.0 and Tornado >= 3.0.

::

    pip install git+https://github.com/saghul/tornaduv.git


**NOTE:** If you are using Tornado 2.4.x you need to use the 'tornado24' branch
or the 0.2.x versions of tornaduv.


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


Author
======

Saúl Ibarra Corretgé <saghul@gmail.com>


License
=======

tornaduv uses the MIT license, check LICENSE file.

