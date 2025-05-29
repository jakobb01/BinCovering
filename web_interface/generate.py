class Generate:
    def start(self):
        raise NotImplementedError("start() must be implemented by subclass")

    def next(self):
        raise NotImplementedError("next() must be implemented by subclass")

    def stop(self):
        raise NotImplementedError("stop() must be implemented by subclass")
