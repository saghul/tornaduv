
import pyuv

import datetime
import errno
import functools
import logging
import numbers
import os

try:
    import thread
except ImportError:
    import _thread as thread  # Python 3

try:
    import signal
except ImportError:
    signal = None

from tornado import stack_context
from tornado.ioloop import IOLoop
from tornado.log import gen_log
from tornado.platform.auto import Waker as FDWaker

__all__ = ('UVLoop')

__version__ = '0.4.0'


class Waker(object):
    def __init__(self, loop):
        self._async = pyuv.Async(loop, lambda x: None)

    def wake(self):
        self._async.send()


class UVLoop(IOLoop):

    def initialize(self, loop=None):
        self._loop = loop or pyuv.Loop()
        self._handlers = {}
        self._callbacks = []
        self._callback_lock = thread.allocate_lock()
        self._timeouts = set()
        self._stopped = False
        self._running = False
        self._closing = False
        self._thread_ident = None
        self._cb_handle = pyuv.Prepare(self._loop)
        self._cb_handle.start(self._prepare_cb)
        self._waker = Waker(self._loop)
        self._fdwaker = FDWaker()
        self._signal_checker = pyuv.util.SignalChecker(self._loop, self._fdwaker.reader.fileno())

    def close(self, all_fds=False):
        with self._callback_lock:
            self._closing = True
        if all_fds:
            for fd in self._handlers:
                obj, _ = self._handlers[fd]
                if obj is not None and hasattr(obj, 'close'):
                    try:
                        obj.close()
                    except Exception:
                        gen_log.debug("error closing socket object %s", obj,
                                      exc_info=True)
                try:
                    os.close(fd)
                except Exception:
                    gen_log.debug("error closing fd %s", fd, exc_info=True)

        self._fdwaker.close()
        self._close_loop_handles()
        # Run the loop so the close callbacks are fired and memory is freed
        self._loop.run()
        self._loop = None

    def add_handler(self, fd, handler, events):
        obj = None
        if hasattr(self, 'split_fd'):
            fd, obj = self.split_fd(fd)
        if fd in self._handlers:
            raise IOError("fd %d already registered" % fd)
        poll = pyuv.Poll(self._loop, fd)
        poll.handler = stack_context.wrap(handler)
        self._handlers[fd] = (obj, poll)
        poll_events = 0
        if events & IOLoop.READ:
            poll_events |= pyuv.UV_READABLE
        if events & IOLoop.WRITE:
            poll_events |= pyuv.UV_WRITABLE
        poll.start(poll_events, self._handle_poll_events)

    def update_handler(self, fd, events):
        if hasattr(self, 'split_fd'):
            fd, _ = self.split_fd(fd)
        _, poll = self._handlers[fd]
        poll_events = 0
        if events & IOLoop.READ:
            poll_events |= pyuv.UV_READABLE
        if events & IOLoop.WRITE:
            poll_events |= pyuv.UV_WRITABLE
        poll.start(poll_events, self._handle_poll_events)

    def remove_handler(self, fd):
        if hasattr(self, 'split_fd'):
            fd, _ = self.split_fd(fd)
        data = self._handlers.pop(fd, None)
        if data is not None:
            _, poll = data
            poll.close()
            poll.handler = None

    def start(self):
        if self._running:
            raise RuntimeError('IOLoop is already running')
        if not logging.getLogger().handlers:
            # The IOLoop catches and logs exceptions, so it's
            # important that log output be visible.  However, python's
            # default behavior for non-root loggers (prior to python
            # 3.2) is to print an unhelpful "no handlers could be
            # found" message rather than the actual log entry, so we
            # must explicitly configure logging if we've made it this
            # far without anything.
            logging.basicConfig()
        if self._stopped:
            self._stopped = False
            return
        old_current = getattr(IOLoop._current, "instance", None)
        IOLoop._current.instance = self
        self._thread_ident = thread.get_ident()

        # pyuv won't interate the loop if the poll is interrupted by
        # a signal, so make sure we can wake it up to catch signals
        # registered with the signal module
        #
        # If someone has already set a wakeup fd, we don't want to
        # disturb it.  This is an issue for twisted, which does its
        # SIGCHILD processing in response to its own wakeup fd being
        # written to.  As long as the wakeup fd is registered on the IOLoop,
        # the loop will still wake up and everything should work.
        old_wakeup_fd = None
        self._signal_checker.stop()
        if hasattr(signal, 'set_wakeup_fd') and os.name == 'posix':
            # requires python 2.6+, unix.  set_wakeup_fd exists but crashes
            # the python process on windows.
            try:
                old_wakeup_fd = signal.set_wakeup_fd(self._fdwaker.writer.fileno())
                if old_wakeup_fd != -1:
                    # Already set, restore previous value.  This is a little racy,
                    # but there's no clean get_wakeup_fd and in real use the
                    # IOLoop is just started once at the beginning.
                    signal.set_wakeup_fd(old_wakeup_fd)
                    old_wakeup_fd = None
                else:
                    self._signal_checker.start()
            except ValueError:  # non-main thread
                pass

        self._running = True
        self._loop.run(pyuv.UV_RUN_DEFAULT)

        # reset the stopped flag so another start/stop pair can be issued
        self._running = False
        self._stopped = False
        IOLoop._current.instance = old_current
        if old_wakeup_fd is not None:
            signal.set_wakeup_fd(old_wakeup_fd)

    def stop(self):
        self._stopped = True
        self._loop.stop()
        self._waker.wake()

    def add_timeout(self, deadline, callback, *args, **kwargs):
        callback = stack_context.wrap(callback)
        if callable(callback):
            callback = functools.partial(callback, *args, **kwargs)
        timeout = _Timeout(deadline, callback, self)
        self._timeouts.add(timeout)
        return timeout

    def remove_timeout(self, timeout):
        self._timeouts.discard(timeout)
        if timeout._timer:
            timeout._timer.stop()

    def add_callback(self, callback, *args, **kwargs):
        with self._callback_lock:
            if self._closing:
                raise RuntimeError("IOLoop is closing")
            empty = not self._callbacks
            self._callbacks.append(functools.partial(stack_context.wrap(callback), *args, **kwargs))
        if empty or thread.get_ident() != self._thread_ident:
            self._waker.wake()

    def add_callback_from_signal(self, callback, *args, **kwargs):
        with stack_context.NullContext():
            if thread.get_ident() != self._thread_ident:
                # if the signal is handled on another thread, we can add
                # it normally (modulo the NullContext)
                self.add_callback(callback, *args, **kwargs)
            else:
                # If we're on the IOLoop's thread, we cannot use
                # the regular add_callback because it may deadlock on
                # _callback_lock.  Blindly insert into self._callbacks.
                # This is safe because the GIL makes list.append atomic.
                # One subtlety is that if the signal interrupted the
                # _callback_lock block in IOLoop.start, we may modify
                # either the old or new version of self._callbacks,
                # but either way will work.
                self._callbacks.append(functools.partial(stack_context.wrap(callback), *args, **kwargs))
                self._waker.wake()

    def _handle_poll_events(self, handle, poll_events, error):
        events = 0
        if error is not None:
            # Some error was detected, signal readability and writability so that the
            # handler gets and handles the error
            events |= IOLoop.READ | IOLoop.WRITE
        else:
            if poll_events & pyuv.UV_READABLE:
                events |= IOLoop.READ
            if poll_events & pyuv.UV_WRITABLE:
                events |= IOLoop.WRITE
        fd = handle.fileno()
        try:
            obj, poll = self._handlers[fd]
            callback_fd = fd
            if obj is not None and hasattr(obj, 'fileno'):
                # socket object was passed to add_handler,
                # return it to the callback
                callback_fd = obj

            poll.handler(callback_fd, events)
        except (OSError, IOError) as e:
            if e.args[0] == errno.EPIPE:
                # Happens when the client closes the connection
                pass
            else:
                logging.error("Exception in I/O handler for fd %s", fd, exc_info=True)
        except Exception:
            logging.error("Exception in I/O handler for fd %s", fd, exc_info=True)

    def _prepare_cb(self, handle):
        with self._callback_lock:
            callbacks = self._callbacks
            self._callbacks = []
        for callback in callbacks:
            self._run_callback(callback)

    def _close_loop_handles(self):
        for handle in self._loop.handles:
            if not handle.closed:
                handle.close()


class _Timeout(object):
    """An IOLoop timeout, a UNIX timestamp and a callback"""

    __slots__ = ['deadline', 'callback', '_timer']

    def __init__(self, deadline, callback, io_loop):
        now = io_loop.time()
        if isinstance(deadline, numbers.Real):
            self.deadline = deadline
        elif isinstance(deadline, datetime.timedelta):
            self.deadline = now + _Timeout.timedelta_to_seconds(deadline)
        else:
            raise TypeError("Unsupported deadline %r" % deadline)
        self.callback = callback
        timeout = max(self.deadline - now, 0)
        self._timer = pyuv.Timer(io_loop._loop)
        self._timer.start(self._timer_cb, timeout, 0.0)

    def _timer_cb(self, handle):
        self._timer.close()
        self._timer = None
        io_loop = IOLoop.current()
        io_loop._timeouts.remove(self)
        io_loop._run_callback(self.callback)

    @staticmethod
    def timedelta_to_seconds(td):
        """Equivalent to td.total_seconds() (introduced in python 2.7)."""
        return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10 ** 6) / float(10 ** 6)
