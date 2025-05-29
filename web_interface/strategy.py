# strategy.py
import os

class Strategy:
    def __init__(self, filename=None, path="./src/data/"):
        self.file = None
        self.log_path = path  # Store path for later use
        if filename:
            self.log(filename)

    def start(self):
        raise NotImplementedError("start() must be implemented by subclass")

    def log(self, filename):
        full_path = os.path.join(self.log_path, filename)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        self.file = open(full_path, 'w')

    def next(self):
        raise NotImplementedError("next() must be implemented by subclass")

    def stop(self):
        raise NotImplementedError("stop() must be implemented by subclass")
