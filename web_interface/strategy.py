# strategy.py

class Strategy:
    def __init__(self, filename=None):
        self.file = None
        if filename:
            self.log(filename)

    def start(self):
        raise NotImplementedError("start() must be implemented by subclass")

    def log(self, filename):
        self.file = open(filename, 'w')

    def next(self):
        raise NotImplementedError("next() must be implemented by subclass")

    def stop(self):
        raise NotImplementedError("stop() must be implemented by subclass")
