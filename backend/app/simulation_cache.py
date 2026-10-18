"""One parsed immutable result, released after idle; no mutation of reader references."""
import threading
import time


class IdleResultCache:
    def __init__(self, idle_seconds=30., clock=time.monotonic):
        self.idle_seconds = idle_seconds
        self.clock = clock
        self.lock = threading.Lock()
        self.entry = None
        self.last_access = 0.
        self.timer = None

    def _schedule(self, delay):
        self.timer = threading.Timer(delay, self.expire)
        self.timer.daemon = True
        self.timer.start()

    def expire(self):
        with self.lock:
            self.timer = None
            remaining = self.idle_seconds-(self.clock()-self.last_access)
            if self.entry is not None and remaining > 0:
                self._schedule(remaining)
            else:
                self.entry = None

    def get(self, id, load):
        with self.lock:
            if self.entry is None or self.entry[0] != id:
                # Release the previous cache reference before parsing another result.
                self.entry = None
                self.entry = (id, load())
            self.last_access = self.clock()
            if self.timer is None:
                self._schedule(self.idle_seconds)
            return self.entry[1]

    def status(self):
        with self.lock:
            return {'entries': int(self.entry is not None), 'idleSeconds': self.idle_seconds}

    def close(self):
        with self.lock:
            if self.timer:
                self.timer.cancel()
                self.timer = None
            self.entry = None
