import queue
import curses

#from .WorkerManager import WorkerManager
#from .ResponseDBManager import ResponseDBManager
from WorkerManager import *
from ResponseDBManager import *

from time import sleep





import random


class OmenEye:
    def __init__(self, db_name):

        NumRequestBuilders = 6
        NumRequestWorkers = 5
        NumRequestParsers = 3
        NumDBWorkers = 1

        self.url_queue = queue.Queue()
        self.request_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.results_queue = queue.Queue()


        for _ in range(10000):
            for letter in range(ord('a'), ord('z') + 1):
                self.url_queue.put(chr(letter))


        self.RequestBuilders = WorkerManager(
            worker_func=self.request_builder,
            num_threads=NumRequestBuilders,
            input_queue=self.url_queue,
            output_queue=self.request_queue
        )
        self.RequestWorkers = WorkerManager(
            worker_func=self.request_worker,
            num_threads=NumRequestWorkers,
            input_queue=self.request_queue,
            output_queue=self.response_queue
        )
        self.RequestParsers = WorkerManager(
            worker_func=self.request_parser,
            num_threads=NumRequestParsers,
            input_queue=self.response_queue,
            output_queue=self.results_queue
        )
        #self.DBWorkers = ResponseDBManager(
        #    db_name=db_name,
        #    num_threads=NumDBWorkers,
        #    input_queue=self.results_queue
        #)

    def request_builder(self, item):
        s = item.upper()
        sleep(0.03 + random.uniform(0.01, 0.5))
        return s

    def request_worker(self, item):
        s = item + '!'
        sleep(0.12 + random.uniform(0.01, 0.5))
        return s

    def request_parser(self, item):
        # ADD LINKS TO URL QUEUE IN HERE
        s = item + '?'
        if 'H' in item:
            self.url_queue.put('a')
        sleep(0.05 + random.uniform(0.01, 0.5))
        return s

    def run(self, stdscr=None):
        try:
            self.RequestBuilders.start_threads()
            self.RequestWorkers.start_threads()
            self.RequestParsers.start_threads()
            #self.DBWorkers.start_threads()

            finished = False

            # Variables to track previous task counts
            prev_url_tasks = self.url_queue.unfinished_tasks
            prev_request_tasks = self.request_queue.unfinished_tasks
            prev_response_tasks = self.response_queue.unfinished_tasks
            prev_results_tasks = self.response_queue.unfinished_tasks
            prev_time = time()

            # Wait for all queue tasks to be finished
            while not finished:
                if stdscr:
                    # Current task counts
                    current_url_tasks = self.url_queue.unfinished_tasks
                    current_request_tasks = self.request_queue.unfinished_tasks
                    current_response_tasks = self.response_queue.unfinished_tasks
                    current_results_tasks = self.results_queue.unfinished_tasks
                    current_time = time()
                    
                    # Calculate time elapsed
                    time_elapsed = current_time - prev_time
                    
                    # Calculate the rate of consumption
                    url_rate = -((prev_url_tasks - current_url_tasks) / time_elapsed)
                    request_rate = -((prev_request_tasks - current_request_tasks) / time_elapsed)
                    response_rate = -((prev_response_tasks - current_response_tasks) / time_elapsed)
                    results_rate = -((prev_results_tasks - current_results_tasks) / time_elapsed)
                    
                    # Display the counts and rates

                    builder_input_rate, builder_output_rate = self.RequestBuilders.get_rates()
                    worker_input_rate, worker_output_rate = self.RequestWorkers.get_rates()
                    parser_input_rate, parser_output_rate = self.RequestParsers.get_rates()
                    #dbworker_input_rate, dbworker_output_rate = self.DBWorkers.get_rates()

                    stdscr.addstr(0, 0, f'URL Queue Tasks Left        : {current_url_tasks:7} ({url_rate:+9.2f} tasks/sec)      ')
                    stdscr.addstr(1, 0, f'Request Queue Tasks Left    : {current_request_tasks:7} ({request_rate:+9.2f} tasks/sec)      ')
                    stdscr.addstr(2, 0, f'Response Queue Tasks Left   : {current_response_tasks:7} ({response_rate:+9.2f} tasks/sec)      ')
                    stdscr.addstr(3, 0, f'Results Queue Tasks Left    : {current_results_tasks:7} ({results_rate:+9.2f} tasks/sec)      ')



                    stdscr.addstr(5, 0, f'RequestBuilder Intake Rate  : {builder_input_rate:9.2f} tasks/sec      ')
                    stdscr.addstr(6, 0, f'RequestBuilder Output Rate  : {builder_output_rate:9.2f} tasks/sec      ')
                    stdscr.addstr(7, 0, f'RequestWorker Intake Rate   : {worker_input_rate:9.2f} tasks/sec      ')
                    stdscr.addstr(8, 0, f'RequestWorker Output Rate   : {worker_output_rate:9.2f} tasks/sec      ')
                    stdscr.addstr(9, 0, f'RequestParser Intake Rate   : {parser_input_rate:9.2f} tasks/sec      ')
                    stdscr.addstr(10, 0, f'RequestParser Output Rate   : {parser_output_rate:9.2f} tasks/sec      ')
                    #stdscr.addstr(0, 0, f'DBWorker Intake Rate        : {dbworker_input_rate:9.2f} tasks/sec      ')                    
                    #stdscr.addstr(0, 0, f'DBWorker Output Rate        : {dbworker_output_rate:9.2f} tasks/sec      ')


                    #stdscr.addstr(5, 0, f'RequestBuilder Intake Rate  : {builder_input_rate:9.2f} tasks/sec      ')
                    #stdscr.addstr(6, 0, f'RequestWorker Intake Rate   : {worker_input_rate:9.2f} tasks/sec      ')
                    #stdscr.addstr(7, 0, f'RequestParser Intake Rate   : {parser_input_rate:9.2f} tasks/sec      ')
                    #stdscr.addstr(0, 0, f'DBWorker Intake Rate        : {dbworker_input_rate:9.2f} tasks/sec      ')

                    #stdscr.addstr(8, 0, f'RequestBuilder Output Rate  : {builder_output_rate:9.2f} tasks/sec      ')
                    #stdscr.addstr(9, 0, f'RequestWorker Output Rate   : {worker_output_rate:9.2f} tasks/sec      ')
                    #stdscr.addstr(10, 0, f'RequestParser Output Rate   : {parser_output_rate:9.2f} tasks/sec      ')
                    #stdscr.addstr(0, 0, f'DBWorker Output Rate        : {dbworker_output_rate:9.2f} tasks/sec      ')
                    
                    # Refresh the screen to update the changes
                    stdscr.refresh()

                    # Update previous task counts and time
                    prev_url_tasks = current_url_tasks
                    prev_request_tasks = current_request_tasks
                    prev_response_tasks = current_response_tasks
                    prev_results_tasks = current_results_tasks
                    prev_time = current_time

                url_q = self.url_queue.unfinished_tasks == 0
                request_q = self.request_queue.unfinished_tasks == 0
                response_q = self.response_queue.unfinished_tasks == 0

                if url_q and request_q and response_q:
                    finished = True

                sleep(1)
        except KeyboardInterrupt:
            pass

        self.RequestBuilders.stop_threads()
        self.RequestWorkers.stop_threads()
        self.RequestParsers.stop_threads()
        #self.DBWorkers.join_threads()

    def run_live(self):
        curses.wrapper(self.run)

    

oe = OmenEye('test')
oe.run_live()

for _ in range(oe.results_queue.qsize()):
    r = oe.results_queue.get()
    #print(r)
