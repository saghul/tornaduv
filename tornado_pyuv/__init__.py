
import pyuv

import datetime
import errno
import logging
import os
import time
import thread

try:
    import signal
except ImportError:
    signal = None

from collections import deque
from tornado import ioloop, stack_context
from tornado.platform.auto import Waker as FDWaker


class Waker(object):
    def __init__(self, loop):
        self._async = pyuv.Async(loop, lambda x: None)
        self._async.unref()
    def wake(self):
        self._async.send()


class IOLoop(object):
    NONE = ioloop.IOLoop.NONE
    READ = ioloop.IOLoop.READ
    WRITE = ioloop.IOLoop.WRITE
    ERROR = ioloop.IOLoop.ERROR

    _instance_lock = thread.allocate_lock()

    def __init__(self, impl=None):
        if impl is not None:
            raise RuntimeError('When using pyuv the poller implementation cannot be specifiedi')
        self._loop = pyuv.Loop()
        self._handlers = {}
        self._callbacks = deque()
        self._callback_lock = thread.allocate_lock()
        self._timeouts = set()
        self._running = False
        self._stopped = False
        self._thread_ident = None
        self._cb_handle = pyuv.Prepare(self._loop)
        self._waker = Waker(self._loop)
        self._fdwaker = FDWaker()
        self._signal_checker = pyuv.util.SignalChecker(self._loop, self._fdwaker.reader.fileno())
        self._signal_checker.unref()

    @staticmethod
    def instance():
        if not hasattr(IOLoop, "_instance"):
            with IOLoop._instance_lock:
                if not hasattr(IOLoop, "_instance"):
                    # New instance after double check
                    IOLoop._instance = IOLoop()
        return IOLoop._instance

    @staticmethod
    def initialized():
        """Returns true if the singleton instance has been created."""
        return hasattr(IOLoop, "_instance")

    def install(self):
        """Installs this IOLoop object as the singleton instance.

        This is normally not necessary as `instance()` will create
        an IOLoop on demand, but you may want to call `install` to use
        a custom subclass of IOLoop.
        """
        assert not IOLoop.initialized()
        IOLoop._instance = self

    def _close_loop_handles(self):
        def cb(handle):
            if not handle.closed:
                handle.close()
        self._loop.walk(cb)

    def close(self, all_fds=False):
        # NOTE: all_fds is disregarded, everything is closed
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
        poll.fd = fd
        self._handlers[fd] = (poll, stack_context.wrap(handler))
        poll_events = 0
        if events & IOLoop.READ:
            poll_events |= pyuv.UV_READABLE
        if events & IOLoop.WRITE:
            poll_events |= pyuv.UV_WRITABLE
        poll.start(poll_events, self._handle_poll_events)

    def update_handler(self, fd, events):
        poll, _ = self._handlers[fd]
        poll_events = 0
        if events & IOLoop.READ:
            poll_events |= pyuv.UV_READABLE
        if events & IOLoop.WRITE:
            poll_events |= pyuv.UV_WRITABLE
        poll.start(poll_events, self._handle_poll_events)

    def remove_handler(self, fd):
        self._handlers.pop(fd, None)

    def set_blocking_signal_threshold(self, seconds, action):
        raise NotImplementedError

    def set_blocking_log_threshold(self, seconds):
        raise NotImplementedError

    def log_stack(self, signal, frame):
        raise NotImplementedError

    def start(self):
        if self._stopped:
            self._stopped = False
            return
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
            # We should use run() here, but we'd need to have break() for that
            self._loop.run(pyuv.UV_RUN_ONCE)
        # reset the stopped flag so another start/stop pair can be issued
        self._stopped = False

    def stop(self):
        self._running = False
        self._stopped = True
        self._waker.wake()

    def running(self):
        """Returns true if this IOLoop is currently running."""
        return self._running

    def add_timeout(self, deadline, callback):
        timeout = _Timeout(deadline, stack_context.wrap(callback), io_loop=self)
        self._timeouts.add(timeout)
        return timeout

    def remove_timeout(self, timeout):
        self._timeouts.remove(timeout)
        timer = timeout._timer
        if timer.active:
            timer.stop()

    def add_callback(self, callback):
        with self._callback_lock:
            was_active = self._cb_handle.active
            self._callbacks.append(stack_context.wrap(callback))
            if not was_active:
                self._cb_handle.start(self._prepare_cb)
        if not was_active or thread.get_ident() != self._thread_ident:
            self._waker.wake()

    def handle_callback_exception(self, callback):
        """This method is called whenever a callback run by the IOLoop
        throws an exception.

        By default simply logs the exception as an error.  Subclasses
        may override this method to customize reporting of exceptions.

        The exception itself is not passed explicitly, but is available
        in sys.exc_info.
        """
        logging.error("Exception in callback %r", callback, exc_info=True)

    def _run_callback(self, callback):
        try:
            callback()
        except Exception:
            self.handle_callback_exception(callback)

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
        fd = handle.fd
        try:
            self._handlers[fd][1](fd, events)
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


class _Timeout(object):
    """An IOLoop timeout, a UNIX timestamp and a callback"""

    # Reduce memory overhead when there are lots of pending callbacks
    __slots__ = ['deadline', 'callback', 'io_loop', '_timer']

    def __init__(self, deadline, callback, io_loop=None):
        if isinstance(deadline, (int, long, float)):
            self.deadline = deadline
        elif isinstance(deadline, datetime.timedelta):
            self.deadline = time.time() + _Timeout.timedelta_to_seconds(deadline)
        else:
            raise TypeError("Unsupported deadline %r" % deadline)
        self.callback = callback
        self.io_loop = io_loop or IOLoop.instance()
        timeout = max(self.deadline - time.time(), 0)
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


class PeriodicCallback(object):
    def __init__(self, callback, callback_time, io_loop=None):
        self.callback = callback
        self.callback_time = callback_time / 1000.0
        self.io_loop = io_loop or IOLoop.instance()
        self._timer = pyuv.Timer(self.io_loop._loop)
        self._running = False

    def _timer_cb(self, timer):
        try:
            self.callback()
        except Exception:
            logging.error("Error in periodic callback", exc_info=True)

    def start(self):
        if self._running:
            return
        self._running = True
        self._timer.start(self._timer_cb, self.callback_time, self.callback_time)
        self._timer.repeat = self.callback_time

    def stop(self):
        if not self._running:
            return
        self._running = False
        self._timer.stop()


def install():
    # Patch Tornado's classes with ours
    ioloop.IOLoop = IOLoop
    ioloop._Timeout = _Timeout
    ioloop.PeriodicCallback = PeriodicCallback

