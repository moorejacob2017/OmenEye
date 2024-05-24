import threading
import queue
from time import time, sleep


'''
# Nice way to "checkout" a resource with a block
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


'''
WorkerMangager
__init__
    worker_func - funtion to run as workers
    num_threads - number of workers/threads to make
    input_queue - the queue workers get input from
    output_queue - the queue worker put their results

start_threads - start the threads
stop_threads - kill threads, use in emergencies
join_threads - join the threads when input queue is empty
worker - (do not use) the worker wrapper used to run the worker func and handle input/output 
get_rates - get intake and output rates of workers
'''
class WorkerManager:
    def __init__(self,
            worker_func=None,
            num_threads=None,
            input_queue=None,
            output_queue=None,
        ):
        
        if worker_func is None or not callable(worker_func):
            raise TypeError(f"worker_func should be of type 'callable', but got {type(worker_func).__name__}")
        if num_threads is None or not isinstance(num_threads, int):
            raise TypeError(f"num_threads should be of type 'int', but got {type(num_threads).__name__}")
        if input_queue is None or not isinstance(input_queue, queue.Queue):
            raise TypeError(f"input_queue should be of type 'queue.Queue', but got {type(input_queue).__name__}")
        if output_queue is None or not isinstance(output_queue, queue.Queue):
            raise TypeError(f"output_queue should be of type 'queue.Queue', but got {type(output_queue).__name__}")

        self.worker_func = worker_func
        self.num_threads = num_threads
        self.input_queue = input_queue
        self.output_queue = output_queue

        self.threads = []
        self.stop_threads_event = threading.Event()
        #self.mutex = threading.Lock()

        self.last_output_time = 0
        self.last_input_time = 0
        self.input_ema = 0.0
        self.output_ema = 0.0
        
        #A higher alpha (e.g., 0.3) means the rate will adjust more quickly to recent changes.
        self.alpha = 0.01  # EMA smoothing factor

        self.lock = threading.Lock()

    def start_threads(self):
        worker_id = 0
        for _ in range(self.num_threads):
            thread = threading.Thread(target=self.worker, args=(worker_id,))
            thread.start()
            self.threads.append(thread)
            worker_id += 1

    # Useful for situations where you want to keep threads up
    # while the input queue is empty
    # (eg. call start_threads and then stop_threads when you
    #  you want to stop them)
    def stop_threads(self):
        self.stop_threads_event.set()

        for thread in self.threads:
            thread.join()

    # Automatically stop all threads when all tasks are 
    # done on the input queue
    # Otherwise, wait for more input on the input queue
    def join_threads(self):
        size = 0

        while self.input_queue.unfinished_tasks > 0:
            sleep(1)
            #size = self.input_queue.qsize()
            #print('[*] WorkerManager: Items left in Input Queue -', size)
            #print('[*] WorkerManager: Items left in Output Queue -', self.output_queue.qsize())
        
        self.stop_threads()

    def worker(self, worker_id):
        while not self.stop_threads_event.is_set():
            try:
                item = self.input_queue.get(timeout=1)

                if not self.stop_threads_event.is_set():
                    result = self.worker_func(item)
                    if result:
                        with self.lock:
                            current_time = time()
                            time_diff = current_time - self.last_output_time
                            self.output_ema = self.alpha * (1 / time_diff) + (1 - self.alpha) * self.output_ema
                            self.last_output_time = current_time
                        self.output_queue.put(result)

                with self.lock:
                    current_time = time()
                    time_diff = current_time - self.last_input_time
                    self.input_ema = self.alpha * (1 / time_diff) + (1 - self.alpha) * self.input_ema
                    self.last_input_time = current_time
                self.input_queue.task_done()
            except queue.Empty:
                pass

    def get_rates(self):
        with self.lock:
            input_rate = self.input_ema
            output_rate = self.output_ema
        return input_rate, output_rate