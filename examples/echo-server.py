
import tornado_pyuv
tornado_pyuv.install()

from tornado import ioloop
from tornado import netutil


class EchoServer(netutil.TCPServer):

    def handle_stream(self, stream, address):
        self._stream = stream
        self._read_line()

    def _read_line(self):
        self._stream.read_until('\n', self._handle_read)

    def _handle_read(self, data):
        self._stream.write(data)
        self._read_line()


if __name__ == '__main__':
    server = EchoServer()
    server.listen(8889)
    ioloop.IOLoop.instance().start()

