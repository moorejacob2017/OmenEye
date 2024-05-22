import os
import threading
import queue
import sqlite3
from time import time, sleep


import requests

#from RequestUtils import *
from .RequestUtils import *


#https://peps.python.org/pep-0703/

class DummyResponse:
    def __init__(self, response=None, content=b'', get_rendered=False):
        if response:
            self.url = str(response.request.url)
            self.visited = True
            self.status_code = int(response.status_code)
            self.content = bytes(content)
            self.headers = dict(response.headers)
            self.text = get_text(response, content)

            if get_rendered:
                self.links = get_links(response, content)
            else:
                self.links = get_links(response, content)

            self.query_params = get_qps(self.url)
            self.inputs = get_inputs(response, content)
            self.is_redirect = bool(response.is_redirect)
        else:
            self.url = None
            self.visited = False
            self.status_code = None
            self.content = None
            self.headers = {}
            self.text = None
            self.links = []
            self.query_params = []
            self.inputs = []
            self.is_redirect = None
    
    '''Use for urls that have been seen but are unvisited'''
    def blank_w_url(self, url):
        self.url = str(url)
        self.query_params = get_qps(self.url)
        return self


'''
ThreadSafeCounter
    Used to increment SQL Primary Keys across multiple DBs.
    Makes it easier when merging
'''
class ThreadSafeCounter:
    def __init__(self):
        self.value = 0
        self.lock = threading.Lock()

    def increment(self):
        with self.lock:
            self.value += 1

    def decrement(self):
        with self.lock:
            self.value -= 1

    def get_value(self):
        with self.lock:
            self.value += 1
            return self.value


'''
ResponseDBManager
    Used to add responses to an sqlite3 db
    Is multithreaded and writes to multiple dbs at once
    to make it faster. Merges the dbs afterwards.

__init__
    db_name - Name of the DB to make
    num_threads - number of threads to run with
    input_queue - a queue of responses to pull from

start_threads - start the threads
stop_threads - kill threads, use in emergencies
join_threads - join the threads when input queue is empty
combine_dbs - (Dont call) Combine the dbs
worker - (Dont call) Worker thread used to get responses from queue and write to db
create_dbs - (Dont call)
init_tables - (Dont call)
write_response_to_db - (Dont call) Write a response to a db, called in worker
get_rates - get intake and output rates of workers
'''
class ResponseDBManager:
    def __init__(self,
            db_name=None,
            num_threads=None,
            input_queue=None,
        ):

        if db_name is None or not isinstance(db_name, str):
            raise TypeError(f"db_name should be of type 'str', but got {type(db_name).__name__}")
        if num_threads is None or not isinstance(num_threads, int):
            raise TypeError(f"num_threads should be of type 'int', but got {type(num_threads).__name__}")
        if input_queue is None or not isinstance(input_queue, queue.Queue):
            raise TypeError(f"input_queue should be of type 'queue.Queue', but got {type(input_queue).__name__}")

        self.responses_pk = ThreadSafeCounter()
        self.headers_pk = ThreadSafeCounter()
        self.links_pk = ThreadSafeCounter()
        self.query_params_pk = ThreadSafeCounter()
        self.inputs_pk = ThreadSafeCounter()

        self.db_name = db_name
        self.num_threads = num_threads
        self.input_queue = input_queue

        self.db_list = []
        for i in range(0, self.num_threads):
            self.db_list.append(f"{db_name}_{i}")

        self.threads = []
        self.stop_threads_event = threading.Event()

        self.last_output_time = 0
        self.last_input_time = 0
        self.input_ema = 0.0
        self.output_ema = 0.0

        #A higher alpha (e.g., 0.3) means the rate will adjust more quickly to recent changes.
        self.alpha = 0.1  # EMA smoothing factor

        self.lock = threading.Lock()


        self.create_dbs()
        self.init_tables()

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

        self.combine_dbs()

    # Automatically stop all threads when all tasks are 
    # done on the input queue
    # Otherwise, wait for more input on the input queue
    def join_threads(self):
        while self.input_queue.unfinished_tasks > 0:
            sleep(5)
        self.stop_threads()

    def worker(self, worker_id):
        commit_counter = 1
        db_name = f"{self.db_name}_{worker_id}"
        with sqlite3.connect(db_name) as conn:
            cursor = conn.cursor()

            while not self.stop_threads_event.is_set():
                try:
                    item = self.input_queue.get(timeout=1)

                    if not self.stop_threads_event.is_set():
                        with self.lock:
                            current_time = time()
                            time_diff = current_time - self.last_output_time
                            self.output_ema = self.alpha * (1 / time_diff) + (1 - self.alpha) * self.output_ema
                            self.last_output_time = current_time
                        self.write_response_to_db(cursor, item)

                    # Push changes every 500 items
                    if commit_counter % 500 == 0:
                        conn.commit()
                        #print(f'[*] DBWorkerManager-W{worker_id}: Committed')
                        commit_counter = 0
                    commit_counter += 1

                    del item

                    with self.lock:
                        current_time = time()
                        time_diff = current_time - self.last_input_time
                        self.input_ema = self.alpha * (1 / time_diff) + (1 - self.alpha) * self.input_ema
                        self.last_input_time = current_time
                    self.input_queue.task_done()
                except queue.Empty:
                    pass

            conn.commit()

    def create_dbs(self):
        for db in self.db_list:
            # Create a new connection to the SQLite database (either newly created or cleared)
            try:
                conn = sqlite3.connect(db, timeout=5000) # timeout in milliseconds (5000ms = 5s)
                conn.execute('PRAGMA foreign_keys = ON;')  # Enable foreign key constraints
                conn.commit()
                conn.close()
                return True
            except sqlite3.Error as e:
                raise Exception(f"Error creating SQLite database: {e}")
            
    def init_tables(self):
        create_responses_table = '''
                CREATE TABLE responses (
                    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT,
                    visited INTEGER,
                    status_code INTEGER,
                    body BLOB
                )
            '''
        create_headers_table = '''
            CREATE TABLE headers (
                header_id INTEGER PRIMARY KEY AUTOINCREMENT,
                response_id INTEGER,
                header_name TEXT,
                header_value TEXT,
                FOREIGN KEY (response_id) REFERENCES responses(response_id)
            )
        '''
        create_links_table = '''
            CREATE TABLE links (
                link_id INTEGER PRIMARY KEY AUTOINCREMENT,
                response_id INTEGER,
                link TEXT,
                FOREIGN KEY (response_id) REFERENCES responses(response_id)
            )
        '''
        create_query_params_table = '''
            CREATE TABLE query_params (
                param_id INTEGER PRIMARY KEY AUTOINCREMENT,
                response_id INTEGER,
                param_name TEXT,
                param_value TEXT,
                FOREIGN KEY (response_id) REFERENCES responses(response_id)
            )
        '''
        create_inputs_table = '''
            CREATE TABLE inputs (
                input_id INTEGER PRIMARY KEY AUTOINCREMENT,
                response_id INTEGER,
                tag TEXT,
                tag_name TEXT,
                tag_value TEXT,
                FOREIGN KEY (response_id) REFERENCES responses(response_id)
            )
        '''

        for db in self.db_list:
            with sqlite3.connect(db) as conn:
                conn.execute(create_responses_table)
                conn.execute(create_headers_table)
                conn.execute(create_links_table)
                conn.execute(create_query_params_table)
                conn.execute(create_inputs_table)
                conn.commit()
        
    def write_response_to_db(self, cursor, response):
        #self.responses_pk = ThreadSafeCounter()
        #self.headers_pk = ThreadSafeCounter()
        #self.links_pk = ThreadSafeCounter()
        #self.query_params_pk = ThreadSafeCounter()
        #self.inputs_pk = ThreadSafeCounter()

        #----------------------------------------------------
        # RESPONSE
        response_id = self.responses_pk.get_value()

        url = response.url
        visited = response.visited
        status_code = response.status_code
        body = response.content

        insert_reponse = '''
            INSERT INTO responses (response_id, url, visited, status_code, body)
            VALUES (?, ?, ?, ?, ?)
        '''
        
        cursor.execute(insert_reponse, (response_id, url, visited, status_code, body))

        #----------------------------------------------------
        # HEADERS
        for header_name in response.headers:
            header_id = self.headers_pk.get_value()
            header_value = response.headers[header_name]
            insert_header = '''
                INSERT INTO headers (header_id, response_id, header_name, header_value)
                VALUES (?, ?, ?, ?)
            '''
            cursor.execute(insert_header, (header_id, response_id, header_name, header_value))

        #----------------------------------------------------
        # LINKS
        links = response.links
        for link in links:
            link_id = self.links_pk.get_value()
            insert_links = '''
                INSERT INTO links (link_id, response_id, link)
                VALUES (?, ?, ?)
            '''
            cursor.execute(insert_links, (link_id, response_id, link))

        #----------------------------------------------------
        # QUERY PARAMS
        qps = response.query_params
        for qp in qps:
            param_id = self.query_params_pk.get_value()
            insert_qp = '''
                INSERT INTO query_params (param_id, response_id, param_name, param_value)
                VALUES (?, ?, ?, ?)
            '''
            cursor.execute(insert_qp, (param_id, response_id, qp[0], qp[1]))

        #----------------------------------------------------
        # INPUTS
        inputs = response.inputs
        for inp in inputs:
            tag, tag_name, tag_value = inp
            input_id = self.inputs_pk.get_value()
            insert_inputs = '''
                INSERT INTO inputs (input_id, response_id, tag, tag_name, tag_value)
                VALUES (?, ?, ?, ?, ?)
            '''
            cursor.execute(insert_inputs, (input_id, response_id, tag, tag_name, tag_value))

        return None

    def combine_dbs(self):
        # Connect to the output database (it will be created if it does not exist)
        source_dbs = self.db_list
        destination_db = self.db_name

        if not os.path.exists(destination_db):
            # If destination DB doesn't exist, initialize it with tables from the first source DB
            with sqlite3.connect(source_dbs[0]) as conn_source:
                with sqlite3.connect(destination_db) as conn_dest:
                    conn_source.backup(conn_dest)
            if len(source_dbs) == 1:
                source_dbs = []
            else:
                source_dbs = source_dbs[1:]
        
        # Connect to the destination DB
        with sqlite3.connect(destination_db) as conn_dest:
            conn_dest.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
            for source_db in source_dbs:
                if source_db == destination_db:
                    continue  # Skip merging if source and destination are the same
                    
                with sqlite3.connect(source_db) as conn_source:
                    # Get the table names from the source DB
                    cursor_source = conn_source.cursor()
                    cursor_source.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='sqlite_sequence'")
                    tables = cursor_source.fetchall()
                    
                    # Merge tables from source DB to destination DB
                    cursor_dest = conn_dest.cursor()
                    for table in tables:
                        table_name = table[0]
                        cursor_source.execute(f"SELECT * FROM {table_name}")
                        rows = cursor_source.fetchall()
                        if not rows == []:
                            cursor_dest.executemany(f"INSERT INTO {table_name} VALUES ({','.join(['?']*len(rows[0]))})", rows)
            
            conn_dest.commit()

        for db in self.db_list:
            try:
                os.remove(db)
                #print(f"File {db} has been removed successfully.")
            except FileNotFoundError:
                print(f"File {db} not found.")
            except PermissionError:
                print(f"Permission denied: {db}")
            except Exception as e:
                print(f"Error removing file {db}: {e}")

    def get_rates(self):
        with self.lock:
            input_rate = self.input_ema
            output_rate = self.output_ema
        return input_rate, output_rate