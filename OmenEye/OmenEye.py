import queue
import curses
import requests
import time
import threading
from .WorkerManager import WorkerManager
from .ResponseDBManager import ResponseDBManager, DummyResponse
from .Scope import Scope
from .CooldownLock import CooldownLock
from .Canaries import BasicWAFCanary, AdaptiveWAFCanary
from .GetAuthSession import get_auth_session
from .DriverUtils import DriverCheckoutManager, create_webdriver, create_auth_webdriver, get_rendered_content

from .RequestUtils import *
#Functions imported from RequestUtils
#    same_domain
#    get_inputs
#    get_qps
#    get_links
#    unpack_gz_content
#    is_gz_file
#    get_url_w_request_and_session
#    get_url
#    get_text
#    get_content_with_max_size
#    filter_invalid_urls
#    check_urls_list
#    is_valid_url
#    standardize_url


class OmenEye:
    def __init__(
            self,
            url, 
            db_name, #output

            seed_file=None,

            mitm_port=None,
            max_depth=2, # depth
            delay=None,
            jitter=None,

            robots=False,
            sitemaps=False,
            subdomains=False,
            js_grabbing=False,
            
            unvisited=False,

            blacklist_file=None,

            
            #whitelist_regex=None,
            #blacklist_regex=None,
            #whitelist_file=None,

            canary=None,
            proxy=None,

            render=None,
            headless=None,
            num_drivers=1,
            
            num_request_builders=1, # builders
            num_request_workers=5, # workers
            num_response_parsers=2, # parsers
            num_db_workers=3, # db-workers

        ):

        # Finish DummyResponse and ResponseDBManager
        # Canary
        # Timing (and mutex) and jitter
        # GetAuthSession (and use curses to do it)
        # Seed from file
        # Seen and Visited
        # Max Depth = 2
        # Include the Scope Class
        # Auto seeding
        # Add links functionality back in

        #---------------------------------------
        # PIPELINE
        NumRequestBuilders = num_request_builders
        NumRequestWorkers = num_request_workers
        NumResponseParsers = num_response_parsers
        NumDBWorkers = num_db_workers

        self.url_queue = queue.Queue()
        self.request_queue = queue.Queue()
        self.response_queue = queue.Queue()
        self.results_queue = queue.Queue()

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
        self.ResponseParsers = WorkerManager(
            worker_func=self.response_parser,
            num_threads=NumResponseParsers,
            input_queue=self.response_queue,
            output_queue=self.results_queue
        )
        self.DBWorkers = ResponseDBManager(
            db_name=db_name,
            num_threads=NumDBWorkers,
            input_queue=self.results_queue
        )
        #---------------------------------------
        self.url = url

        self.url_queue.put((url, 0))
        
        self.visited = set()
        self.seen = set()

        self.unvisited = unvisited


        if seed_file:
            with open(seed_file, 'r') as sf:
                url_list = sf.read().strip().split('\n')
            url_list = filter_invalid_urls(url_list)
            for seed_url in url_list:
                self.url_queue.put((seed_url, 0))


        self.MaxDepth = max_depth


        if canary:
            if canary.lower() == 'basic':
                self.canary = BasicWAFCanary(
                    url,
                    canary_check_interval=60
                )
                print('Using Basic HTTP WAF Canary.')
            elif canary.lower() == 'adaptive':
                self.canary = AdaptiveWAFCanary(
                    url,
                    canary_check_interval=60,
                    max_canary_check_interval=21600
                )
                print('Using Adaptive HTTP WAF Canary.')
            else:
                print('Invalid Canary type. Must be "basic" or "adaptive". Got ' + str(canary))
                exit(1)
            # Make sure message is displayed
            time.sleep(5)
        else:
            self.canary = None


        self.scope = Scope(
            url=url,
            subdomains=subdomains,
            js_grabbing=js_grabbing,
        )


        if robots:
            self.scope.add_rules_from_robots()
        if sitemaps:
            self.scope.get_sitemaps_from_robots()
            for smap in self.scope.sitemaps:
                self.url_queue.put((smap, 0))


        if blacklist_file:
            self.scope.add_blacklist_rules_from_file(blacklist_file)


        # Session
        if mitm_port:
            self.session = get_auth_session(port=mitm_port)
        else:
            self.session = requests.Session()
        self.session.keep_alive = False
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36 Edge/12.246'
        self.session.headers.update({'User-Agent': user_agent})


        if proxy:
            proxies = {
                'http': f'http://{proxy}',
                'https': f'http://{proxy}'
            }
            self.session.proxies.update(proxies)


        # If drivers start bottle necking speed, either start
        # using a pool of drivers (resource heavy) or start
        # creating and destroying drivers as needed in the
        # worker threads (might spike hardware if too many
        # drivers are created at once). Currently, only
        # uses drivers when intitial http requests comeback with
        # html, so they are used as needed.
        # Also, consider creating support for Chrome
        # drivers instead of mandatory Firefox drivers.
        # Should be added in DriverUtils
        #   --render {firefox,chrome}
        if render:
            if mitm_port: # If Auth
                auth_drivers = [create_auth_webdriver(url, self.session, headless=headless) for _ in range(num_drivers)]
                self.auth_driver_manager = DriverCheckoutManager(auth_drivers)

                if subdomains: # If subdomains
                    drivers = [create_webdriver(self.session, headless=headless) for _ in range(num_drivers)]
                    self.driver_manager = DriverCheckoutManager(drivers)
                else:
                    self.driver_manager = None

            else:
                self.auth_driver_manager = None
                drivers = [create_webdriver(self.session, headless=headless) for _ in range(num_drivers)]
                self.driver_manager = DriverCheckoutManager(drivers)
        
        else:
            self.auth_driver_manager = None
            self.driver_manager = None


        # Delay and Jitter
        if delay and jitter:
            self.timing_lock = CooldownLock(cooldown_period=delay, max_jitter=jitter)
        elif delay:
            self.timing_lock = CooldownLock(cooldown_period=delay)
        elif jitter:
            self.timing_lock = CooldownLock(cooldown_period=0, max_jitter=jitter)
        else:
            self.timing_lock = None


        

    def request_builder(self, item):
        url, depth = item
        if not url in self.visited and not url.split('#')[0] in self.visited and not url.split('#')[0] + '#' in self.visited:
            self.visited.add(url)
            request = requests.Request('GET', url)
            return (request, depth)
        else:
            return None
        
    def request_worker(self, item):
        request, depth = item
        url = request.url

        # Canary Blocking
        if self.canary:
            while self.canary.is_blocked:
                time.sleep(1)

        if self.timing_lock:
            self.timing_lock.acquire()
        

        response, content = get_url_w_request_and_session(request, self.session)
        if self.driver_manager or self.auth_driver_manager: # If we are rendering
            if not response.is_redirect: # If not a redirect
                if 'Content-Type' in response.headers:
                    content_type = response.headers['Content-Type'].lower()
                elif 'content-type' in response.headers:
                    content_type = response.headers['content-type'].lower()
                else:
                    content_type = ''
                if 'html' in content_type.lower(): # If it should be rendered (html)

                    used_auth = False
                    if same_domain(response.url, self.url):
                        if self.auth_driver_manager:
                            used_auth = True
                            driver = self.auth_driver_manager.checkout()
                        else:
                            driver = self.driver_manager.checkout()
                    else:
                        driver = self.driver_manager.checkout()

                    try: # ALWAYS free the driver after use, no matter what
                        str_content = get_rendered_content(response.url, driver)
                    except:
                        strcontent = ''
                    finally:
                        if used_auth:
                            self.auth_driver_manager.checkin(driver)
                        else:
                            self.driver_manager.checkin(driver)

                    #str_content = get_rendered_content(response.url, self.driver)
                    encoding = response.encoding if response.encoding else 'ISO-8859-1'

                    content = str_content.encode(encoding, errors='replace')
        # This structure is necessary to juggle render, auth, and subdomains
        # since drivers with cookies error out on domains that are not
        # the same as the cookies
        
        if self.timing_lock:
            self.timing_lock.release()
        
        return (response, content, depth)

    def response_parser(self, item):
        response, content, depth = item
        if response:
            # Do not increase depth it was a redirect
            if response.is_redirect:
                depth -= 1

            result_response = DummyResponse(response, content)

            # Avoid any logouts that could kill the session.
            lo = [
                "logout",
                "log-out",
                "log_out",
                "log%20out",
                "log%2520out",
                "log out",
                "signout",
                "sign-out",
                "sign_out",
                "sign%20out",
                "sign%2520out"
                "sign out",
            ]

            #if in_scope and not visited and in_depth
            #   add to url_queue
            #if in_scope and not visited but out of depth
            #   add to seen
            #if in_scope but visited
            #   trash
            #if not in scope but in domain
            #   add to seen
            #if not in scope and not in domain
            #   trash
            for link in result_response.links:
                is_lo = False
                for l in lo:
                    if l in link.lower():
                        is_lo = True

                if self.scope.in_scope(link):
                    # Avoids fragments - fragments cause way too many requests
                    if not link in self.visited and not link.split('#')[0] in self.visited and not link.split('#')[0] + '#' in self.visited:
                        if is_lo:
                            self.seen.add(link)
                        elif depth+1 <= self.MaxDepth:
                            self.url_queue.put((link, depth+1))
                        else:
                            self.seen.add(link)
                else:
                    if self.scope.in_domain(link):
                        self.seen.add(link)
            return result_response
        else:
            return None

    def run(self, stdscr=None):
        try:
            if self.canary:
                if stdscr:
                    stdscr.clear()
                    stdscr.addstr(0, 0, '---------------------------[OMEN EYE]---------------------------')
                    stdscr.addstr(1, 0, 'Canary establishing baseline. Please wait 180-300 seconds...')
                    stdscr.refresh()
                self.canary.start()
            self.RequestBuilders.start_threads()
            self.RequestWorkers.start_threads()
            self.ResponseParsers.start_threads()
            self.DBWorkers.start_threads()
            

            closed_request_threads = False
            finished = False

            # Variables to track previous task counts
            prev_url_tasks = self.url_queue.unfinished_tasks
            prev_request_tasks = self.request_queue.unfinished_tasks
            prev_response_tasks = self.response_queue.unfinished_tasks
            prev_results_tasks = self.response_queue.unfinished_tasks
            prev_time = time.time()

            # Wait for all queue tasks to be finished
            while not finished:

                # Display Information
                if stdscr:
                    stdscr.clear()
                    # Current task counts
                    current_url_tasks = self.url_queue.unfinished_tasks
                    current_request_tasks = self.request_queue.unfinished_tasks
                    current_response_tasks = self.response_queue.unfinished_tasks
                    current_results_tasks = self.results_queue.unfinished_tasks
                    current_time = time.time()
                    
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
                    parser_input_rate, parser_output_rate = self.ResponseParsers.get_rates()
                    dbworker_input_rate, dbworker_output_rate = self.DBWorkers.get_rates()
                    #stdscr.addstr(0, 0, '----------[OMEN EYE]----------')
                    #---------------------------
                    #===========================
                    stdscr.addstr(0, 0, '===========================[ OMEN EYE ]===========================')
                    stdscr.addstr(1, 0, f' URL Queue Tasks Left        : {current_url_tasks:9} ({url_rate:+9.2f} tasks/sec)')
                    stdscr.addstr(2, 0, f' Request Queue Tasks Left    : {current_request_tasks:9} ({request_rate:+9.2f} tasks/sec)')
                    stdscr.addstr(3, 0, f' Response Queue Tasks Left   : {current_response_tasks:9} ({response_rate:+9.2f} tasks/sec)')
                    stdscr.addstr(4, 0, f' Results Queue Tasks Left    : {current_results_tasks:9} ({results_rate:+9.2f} tasks/sec)')

                    stdscr.addstr(6, 0, f' RequestBuilders\' Intake Rate  : {builder_input_rate:9.2f} tasks/sec')
                    stdscr.addstr(7, 0, f' RequestBuilders\' Output Rate  : {builder_output_rate:9.2f} tasks/sec')
                    stdscr.addstr(8, 0, f' RequestWorkers\' Intake Rate   : {worker_input_rate:9.2f} tasks/sec')
                    stdscr.addstr(9, 0, f' RequestWorkers\' Output Rate   : {worker_output_rate:9.2f} tasks/sec')
                    stdscr.addstr(10, 0, f' ResponseParsers\' Intake Rate  : {parser_input_rate:9.2f} tasks/sec')
                    stdscr.addstr(11, 0, f' ResponseParsers\' Output Rate  : {parser_output_rate:9.2f} tasks/sec')
                    stdscr.addstr(12, 0, f' DBWorkers\' Intake Rate        : {dbworker_input_rate:9.2f} tasks/sec')                    
                    stdscr.addstr(13, 0, f' DBWorkers\' Output Rate        : {dbworker_output_rate:9.2f} tasks/sec')
                    stdscr.addstr(14, 0, f'                                                                     ')
                    if self.canary:
                        if self.canary.is_blocked:
                            stdscr.addstr(15, 0, f' Canary says Blocked!                                                ')
                            stdscr.addstr(16, 0, f'                                                                     ')
                        else:
                            stdscr.addstr(15, 0, f'                                                                     ')
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
                results_q = self.results_queue.unfinished_tasks == 0

                # Close request threads when finished, save resources
                if not closed_request_threads:
                    if url_q and request_q and response_q:
                        self.RequestBuilders.stop_threads()
                        self.RequestWorkers.stop_threads()
                        self.ResponseParsers.stop_threads()
                        closed_request_threads = True

                        if self.canary:
                            self.canary.stop()

                        if self.auth_driver_manager:
                            self.auth_driver_manager.stop_drivers()
                        if self.driver_manager:
                            self.driver_manager.stop_drivers()
                        
                        # Add all of the ones that were seen but
                        # where never visited for some reason
                        if self.unvisited:
                            for seen in self.seen:
                                if not seen in self.visited:
                                    if self.scope.subdomains:
                                        self.results_queue.put(DummyResponse().blank_w_url(seen))
                                    else:
                                        if same_domain(self.url, seen):
                                            self.results_queue.put(DummyResponse().blank_w_url(seen))

                
                if url_q and request_q and response_q and results_q:
                    finished = True

                # OUTPUT REFRESH RATE
                time.sleep(0.5)
        except KeyboardInterrupt:
            if stdscr:
                #stdscr.clear()
                stdscr.addstr(17, 0, f' Caught KeyboardInterrupt. Shutting down...')
                stdscr.refresh()

        if self.canary:
            self.canary.stop()
        if self.auth_driver_manager:
            self.auth_driver_manager.stop_drivers()
        if self.driver_manager:
            self.driver_manager.stop_drivers()
        self.RequestBuilders.stop_threads()
        self.RequestWorkers.stop_threads()
        self.ResponseParsers.stop_threads()
        self.DBWorkers.join_threads()

        

    def run_live(self):
        curses.wrapper(self.run)





'''
---------------------------------
TEST 1
1925 requests

NumRequestBuilders = 1
NumRequestWorkers = 5
NumResponseParsers = 1
NumDBWorkers = 1



real	3m34.490s
user	3m29.266s
sys	0m2.849s

---------------------------------
TEST 2
1877 requests

NumRequestBuilders = 1
NumRequestWorkers = 7
NumResponseParsers = 3
NumDBWorkers = 2

~3:20.15

real	3m28.564s
user	3m20.586s
sys	0m3.630s

---------------------------------
TEST 3
540 requests

NumRequestBuilders = 1
NumRequestWorkers = 10
NumResponseParsers = 3
NumDBWorkers = 2

real	1m31.971s
user	1m20.217s
sys	0m1.273s

'''