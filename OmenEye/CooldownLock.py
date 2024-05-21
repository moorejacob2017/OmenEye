import threading
import time
import random

class CooldownLock:
    def __init__(self, cooldown_period, max_jitter=0):
        self.lock = threading.Lock()
        self.cooldown_period = cooldown_period
        self.last_release_time = None
        self.max_jitter = max_jitter

    def acquire(self, blocking=True, timeout=-1):
        jitter = random.uniform(0, self.max_jitter)
        if not blocking:
            if self.lock.acquire(blocking=False):
                return True
            else:
                if self.last_release_time is not None and (time.time() - self.last_release_time) >= (self.cooldown_period + jitter):
                    self.last_release_time = None
                    return self.lock.acquire(blocking=False)
                return False

        while True:
            acquired = self.lock.acquire(timeout=timeout)
            if acquired:
                if self.last_release_time is None or (time.time() - self.last_release_time) >= (self.cooldown_period + jitter):
                    self.last_release_time = None
                    return True
                self.lock.release()
            if timeout != -1:
                time.sleep(0.01)
                timeout -= 0.01
                if timeout <= 0:
                    return False
            else:
                time.sleep(0.01)

    def release(self):
        self.lock.release()
        self.last_release_time = time.time()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

'''
# Example usage
cooldown_lock = CooldownLock(cooldown_period=5, max_jitter=10)  # 5 seconds cooldown

def task():
    with cooldown_lock:
        print(f"Lock acquired by {threading.current_thread().name}")
        time.sleep(2)  # Simulate some work
    print(f"Lock released by {threading.current_thread().name}")

threads = [threading.Thread(target=task) for _ in range(3)]
for thread in threads:
    thread.start()

for thread in threads:
    thread.join()
'''