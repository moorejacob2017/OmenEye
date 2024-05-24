import threading
import time
from typing import Any, List

class CheckoutManager:
    def __init__(self, items: List[Any]):
        self.items = items
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.checked_out = [False] * len(items)

    def checkout(self) -> Any:
        with self.condition:
            while all(self.checked_out):
                self.condition.wait()
            for i, is_checked_out in enumerate(self.checked_out):
                if not is_checked_out:
                    self.checked_out[i] = True
                    print(f"Item {i} checked out.")
                    return self.items[i]

    def checkin(self, item: Any) -> None:
        with self.condition:
            index = self.items.index(item)
            if self.checked_out[index]:
                self.checked_out[index] = False
                print(f"Item {index} checked in.")
                self.condition.notify()

'''
# Example usage
def worker(manager: CheckoutManager, thread_id: int):
    item = manager.checkout()
    print(f"Thread {thread_id} checked out item: {item}")
    time.sleep(1)  # Simulate some work with the item
    manager.checkin(item)
    print(f"Thread {thread_id} checked in item: {item}")

if __name__ == "__main__":
    items = ["item1", "item2", "item3"]
    manager = CheckoutManager(items)

    threads = []
    for i in range(5):
        thread = threading.Thread(target=worker, args=(manager, i))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()
'''