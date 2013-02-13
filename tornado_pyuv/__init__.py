
import pyuv

import datetime
import errno
import functools
import logging
import os
import thread

try:
    import signal
except ImportError:
    signal = None

from collections import deque
from tornado import stack_context
from tornado.ioloop import IOLoop
from tornado.platform.auto import Waker as FDWaker

__all__ = ('UVLoop')

__version__ = '0.3.0.dev'


class Waker(object):
    def __init__(self, loop):
        self._async = pyuv.Async(loop, lambda x: None)
        self._async.unref()
    def wake(self):
        self._async.send()


class UVLoop(IOLoop):

    def initialize(self):
        self._loop = pyuv.Loop()
        self._handlers = {}
        self._callbacks = deque()
        self._callback_lock = thread.allocate_lock()
        self._timeouts = set()
        self._running = False
        self._stopped = False
        self._closing = False
        self._thread_ident = None
        self._cb_handle = pyuv.Prepare(self._loop)
        self._waker = Waker(self._loop)
        self._fdwaker = FDWaker()
        self._signal_checker = pyuv.util.SignalChecker(self._loop, self._fdwaker.reader.fileno())
        self._signal_checker.unref()

    def close(self, all_fds=False):
        # NOTE: all_fds is disregarded, everything is closed
        with self._callback_lock:
            self._closing = True
        self._fdwaker.close()
        self._handlers = {}
        self._close_loop_handles()
        # Run the loop so the close callbacks are fired and memory is freed
        assert not self._loop.run(pyuv.UV_RUN_NOWAIT), "there are pending handles"
        self._loop = None

    def add_handler(self, fd, handler, events):
        if fd in self._handlers:
            raise IOError("fd %d already registered" % fd)
        poll = pyuv.Poll(self._loop, fd)
        poll.handler = stack_context.wrap(handler)
        self._handlers[fd] = poll
        poll_events = 0
        if events & IOLoop.READ:
            poll_events |= pyuv.UV_READABLE
        if events & IOLoop.WRITE:
            poll_events |= pyuv.UV_WRITABLE
        poll.start(poll_events, self._handle_poll_events)

    def update_handler(self, fd, events):
        poll = self._handlers[fd]
        poll_events = 0
        if events & IOLoop.READ:
            poll_events |= pyuv.UV_READABLE
        if events & IOLoop.WRITE:
            poll_events |= pyuv.UV_WRITABLE
        poll.start(poll_events, self._handle_poll_events)

    def remove_handler(self, fd):
        poll = self._handlers.pop(fd, None)
        if poll is not None:
            poll.close()
            poll.handler = None

    def start(self):
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
        self._running = True

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

        while self._running:
            self._loop.run(pyuv.UV_RUN_ONCE)
        # reset the stopped flag so another start/stop pair can be issued
        self._stopped = False
        IOLoop._current.instance = old_current
        if old_wakeup_fd is not None:
            signal.set_wakeup_fd(old_wakeup_fd)

    def stop(self):
        self._running = False
        self._stopped = True
        self._waker.wake()

    def add_timeout(self, deadline, callback):
        timeout = _Timeout(deadline, stack_context.wrap(callback), io_loop=self)
        self._timeouts.add(timeout)
        return timeout

    def remove_timeout(self, timeout):
        self._timeouts.remove(timeout)
        timer = timeout._timer
        timer.stop()

    def add_callback(self, callback, *args, **kwargs):
        with self._callback_lock:
            if self._closing:
                raise RuntimeError("IOLoop is closing")
            was_active = self._cb_handle.active
            self._callbacks.append(functools.partial(stack_context.wrap(callback), *args, **kwargs))
            if not was_active:
                self._cb_handle.start(self._prepare_cb)
        if not was_active or thread.get_ident() != self._thread_ident:
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
                if not self._cb_handle.active:
                    self._cb_handle.start(self._prepare_cb)
                    self._waker.wake()

    def _handle_poll_events(self, handle, poll_events, error):
        events = 0
        if error is not None:
            # Some error was detected, signal readability and writability so that the
            # handler gets and handles the error
            events |= IOLoop.READ
            events |= IOLoop.WRITE
        else:
            if poll_events & pyuv.UV_READABLE:
                events |= IOLoop.READ
            if poll_events & pyuv.UV_WRITABLE:
                events |= IOLoop.WRITE
        fd = handle.fileno()
        try:
            self._handlers[fd].handler(fd, events)
        except (OSError, IOError) as e:
            if e.args[0] == errno.EPIPE:
                # Happens when the client closes the connection
                pass
            else:
                logging.error("Exception in I/O handler for fd %s", fd, exc_info=True)
        except Exception:
            logging.error("Exception in I/O handler for fd %s", fd, exc_info=True)

    def _prepare_cb(self, handle):
        self._cb_handle.stop()
        with self._callback_lock:
            callbacks = self._callbacks
            self._callbacks = deque()
        while callbacks:
            self._run_callback(callbacks.popleft())

    def _close_loop_handles(self):
        def cb(handle):
            if not handle.closed:
                handle.close()
        self._loop.walk(cb)


class _Timeout(object):
    """An IOLoop timeout, a UNIX timestamp and a callback"""

    # Reduce memory overhead when there are lots of pending callbacks
    __slots__ = ['deadline', 'callback', 'io_loop', '_timer']

    def __init__(self, deadline, callback, io_loop):
        now = io_loop.time()
        if isinstance(deadline, (int, long, float)):
            self.deadline = deadline
        elif isinstance(deadline, datetime.timedelta):
            self.deadline = now + _Timeout.timedelta_to_seconds(deadline)
        else:
            raise TypeError("Unsupported deadline %r" % deadline)
        self.callback = callback
        self.io_loop = io_loop or IOLoop.instance()
        timeout = max(self.deadline - now, 0)
        self._timer = pyuv.Timer(self.io_loop._loop)
        self._timer.start(self._timer_cb, timeout, 0.0)

    def _timer_cb(self, handle):
        self._timer.close()
        self._timer = None
        self.io_loop._timeouts.remove(self)
        self.io_loop._run_callback(self.callback)
        self.io_loop = None

    @staticmethod
    def timedelta_to_seconds(td):
        """Equivalent to td.total_seconds() (introduced in python 2.7)."""
        return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10 ** 6) / float(10 ** 6)

