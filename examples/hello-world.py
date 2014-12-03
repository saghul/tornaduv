
import signal

from tornado.ioloop import IOLoop
from tornado.web import Application, RequestHandler

from tornaduv import UVLoop
IOLoop.configure(UVLoop)


def handle_signal(sig, frame):
    loop = IOLoop.instance()
    loop.add_callback(loop.stop)

class MainHandler(RequestHandler):
    def get(self):
        self.write("Hello, world")

application = Application([
    (r"/", MainHandler),
])


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    application.listen(8080)
    loop = IOLoop.instance()
    loop.start()
    loop.close()

