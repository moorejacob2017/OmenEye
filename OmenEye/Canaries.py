import threading
import requests
from time import sleep

#sudo iptables -A INPUT -p tcp --dport 8000 -j DROP
#sudo iptables -D INPUT -p tcp --dport 8000 -j DROP
#sudo iptables -F
'''
awc = BasicWAFCanary('http://127.0.0.1:8000', 0)
awc = BasicWAFCanary('http://127.0.0.1:8000')
awc.start()

try:
    while True:
        print('is_blocked: ', awc.is_blocked)
        sleep(10)
except KeyboardInterrupt:
    print("Keyboard interrupt caught. Exiting...")

awc.stop()
'''

class BasicWAFCanary:
    def __init__(
        self, 
        canary_url,
        canary_check_interval=10,
    ):
        self.is_blocked = False
        
        self.canary_url = canary_url
        self.canary_check_interval = canary_check_interval

        # Requests Baseline used to tell if being blocked or not
        self.canary_baseline = None

        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run_canary)

    def _establish_baseline(self):
        responses = []
        for _ in range(6):
            if not _ == 0:
                sleep(30)
            try:
                #response = requests.get(self.url, timeout=10)
                user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36 Edge/12.246'
                request = requests.Request('GET', url=self.canary_url)
                request.headers['User-Agent'] = user_agent
                with requests.Session() as s:
                    response = s.send(request.prepare(), timeout=30)

                responses.append(response)
            except requests.RequestException as e:
                pass

        if len(responses) < 3:
            raise Exception("Unable to establish a Canary Baseline")
        
        #common_response = {'status_code': None, 'url': None, 'headers': None, 'text': None}
        common_response = {'status_code': None, 'url': None, 'headers': None}
        
        # Check for common status_code, url, and text among the responses
        common_response['status_code'] = responses[0].status_code if all(r.status_code == responses[0].status_code for r in responses) else None
        common_response['url'] = responses[0].url if all(r.url == responses[0].url for r in responses) else None
        #common_response['text'] = responses[0].text if all(r.text == responses[0].text for r in responses) else None
        
        # Check for common headers and their values among the responses
        all_headers = [set(response.headers.keys()) for response in responses]
        common_headers = set.intersection(*all_headers)
        common_header_values = {header: responses[0].headers[header] for header in common_headers if all(r.headers[header] == responses[0].headers[header] for r in responses)}
        
        common_response['headers'] = common_header_values
        
        self.canary_baseline = common_response

    def _is_request_blocked(self, response=None, exception=None):
        """
        Determine if an HTTP request was blocked.
        :param response: Response object from a successful request.
        :param exception: Exception object from a failed request.
        :return: True if blocked, False otherwise.
        """
        if exception:
            return True  # Consider exceptions as blockages

        if self.canary_baseline:
            # Compare response to baseline
            if self.canary_baseline['status_code'] and response.status_code != self.canary_baseline['status_code']:
                return True
            if self.canary_baseline['url'] and response.url != self.canary_baseline['url']:
                return True
            #if self.canary_baseline['text'] and response.text != self.canary_baseline['text']:
            #    return True
            
            # Compare headers
            for header, value in self.canary_baseline['headers'].items():
                if header not in response.headers or response.headers[header] != value:
                    return True
        
        return False

    def start(self):
        """Start the canary thread."""
        self._establish_baseline()
        self._thread.start()

    def stop(self):
        """Stop the canary thread."""
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=60)
    
    def _check(self):
            response = None
            exception = None
            try:
                request = requests.Request('GET', url=self.canary_url)
                request.headers['User-Agent'] = 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/118.0'
                with requests.Session() as s:
                    response = s.send(request.prepare(), timeout=5)

            except requests.RequestException as e:
                exception = e

            if self._is_request_blocked(response, exception):
                self.is_blocked = True

            else:
                self.is_blocked = False

    def _run_canary(self):
        while not self._stop_event.is_set():
            self._check()
            sleep(self.canary_check_interval)




#initial_request_interval : Initial time between requests
# of the crawler. Used to provide recommendations on what to
# set the time between requests to. (eg. increase if getting blocked)
class AdaptiveWAFCanary(BasicWAFCanary):
    def __init__(
        self, 
        canary_url,
        initial_request_interval,
        canary_check_interval=10,
        max_canary_check_interval=300
    ):
        super().__init__(canary_url, canary_check_interval)
        
        # Recommended time between requests
        self.recommended_request_interval = initial_request_interval

        # Baseline interval to revert to after consecutive blocks
        # Gets increased after a drought
        self.base_canary_check_interval = canary_check_interval

        # The max value the canary check interval can be 
        self.max_canary_check_interval = max_canary_check_interval

        # Used to tell if the block was a fluke or if it is consistant
        self.drought = False

        # Number of time canary was blocked in a row
        self.num_consecutive_blocks = 0

        # Number of time canary was blocked in a row
        self._consecutive_block_interval = canary_check_interval

    def _run_canary(self):
        # If blocked 5 times, the we are in a drought and
        #   blocking is happening consistently
        CONSECUTIVE_BLOCK_THRESHOLD = 5

        while not self._stop_event.is_set():
            self._check()

            # If blocked
            if self.is_blocked:
                self.num_consecutive_blocks += 1

                # If 5th consecutive Block
                if self.num_consecutive_blocks >= CONSECUTIVE_BLOCK_THRESHOLD:
                    # Drought detected
                    if not self.drought:
                        self.drought = True
                        if self.recommended_request_interval == 0:
                            self.recommended_request_interval = 1.15
                        else:
                            self.recommended_request_interval += (self.recommended_request_interval * 0.5)
                        #print(f"\033[1;31m[-] Blocking Detected - Increased time between requests to {self.recommended_request_interval}\033[0m")
                    
                    # Drought strats
                    if self.drought:
                        if self._consecutive_block_interval <= 60: # If less than 60 sec then double
                            self._consecutive_block_interval = min(self._consecutive_block_interval * 2, self.max_canary_check_interval)
                        elif self._consecutive_block_interval <= 900: # If the interval is less than 15 min then add 5 min
                            self._consecutive_block_interval = min(self._consecutive_block_interval + 300, self.max_canary_check_interval)
                        elif self._consecutive_block_interval <= 1800: # If the interval is less than 30 min then add 15 min
                            self._consecutive_block_interval = min(self._consecutive_block_interval + 900, self.max_canary_check_interval)
                        elif self._consecutive_block_interval <= 10800: # If the interval is less than 3 hours add 30 min
                            self._consecutive_block_interval = min(self._consecutive_block_interval + 1860, self.max_canary_check_interval)
                        else: # If greater than 3 hours, double each time
                            self._consecutive_block_interval = min(self._consecutive_block_interval * 2, self.max_canary_check_interval)
                    self.canary_check_interval = self._consecutive_block_interval
                    #print(f"\033[1;34m[*] Current Canary Check Interval: {self.canary_check_interval} seconds\033[0m")
            
            else:
                # End of Drought
                #if self.drought:
                    #print(f"\033[1;32m[+] Blocking Stopped - Continuing...\033[0m")
                self.drought = False
                self.canary_check_interval = self.base_canary_check_interval
                self.num_consecutive_blocks = 0

            sleep(self.canary_check_interval)



