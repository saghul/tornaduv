
import signal

from tornado.ioloop import IOLoop
from tornado.tcpserver import TCPServer

from tornaduv import UVLoop
IOLoop.configure(UVLoop)


def handle_signal(sig, frame):
    IOLoop.instance().add_callback(IOLoop.instance().stop)


class EchoServer(TCPServer):

    def handle_stream(self, stream, address):
        self._stream = stream
        self._read_line()

    def _read_line(self):
        self._stream.read_until('\n', self._handle_read)

    def _handle_read(self, data):
        self._stream.write(data)
        self._read_line()


if __name__ == '__main__':
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    server = EchoServer()
    server.listen(8889)
    IOLoop.instance().start()
    IOLoop.instance().close()

