
import tornado_pyuv
tornado_pyuv.install()

import signal

import tornado.ioloop
import tornado.web


def handle_signal(sig, frame):
    tornado.ioloop.IOLoop.instance().add_callback(tornado.ioloop.IOLoop.instance().stop)

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello, world")

application = tornado.web.Application([
    (r"/", MainHandler),
])


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    application.listen(8080)
    tornado.ioloop.IOLoop.instance().start()
    tornado.ioloop.IOLoop.instance().close()

