import os
import threading
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from urllib.parse import urlparse


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


class DriverCheckoutManager:
    def __init__(self, drivers):
        self.drivers = drivers
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.checked_out = [False] * len(self.drivers)

    def checkout(self):
        with self.condition:
            while all(self.checked_out):
                self.condition.wait()
            for i, is_checked_out in enumerate(self.checked_out):
                if not is_checked_out:
                    self.checked_out[i] = True
                    return self.drivers[i]

    def checkin(self, driver):
        with self.condition:
            index = self.drivers.index(driver)
            if self.checked_out[index]:
                self.checked_out[index] = False
                self.condition.notify()
    
    def stop_drivers(self):
        for i in range(len(self.drivers)):
            try:
                self.drivers[i].quit()
            except:
                pass

def create_webdriver(session=None, headless=True):
    options = webdriver.FirefoxOptions()

    # Add proxies if set
    if session:
        if not session.proxies == {}:
            proxy = urlparse(session.proxies.get('http')).netloc
            proxy_host = proxy.split(':')[0]
            proxy_port = int(proxy.split(':')[1])

            options.set_preference("network.proxy.type", 1)
            options.set_preference("network.proxy.http", proxy_host)
            options.set_preference("network.proxy.http_port", proxy_port)
            options.set_preference("network.proxy.ssl", proxy_host)
            options.set_preference("network.proxy.ssl_port", proxy_port)
    
    # Ignore Cert Issues
    options.set_preference("network.captive-portal-service.enabled", False)
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors')
    options.add_argument('--disable-infobars')
    options.add_argument('--ignore-certificate-errors-spki-list')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--disable-web-security')
    if headless:
        options.add_argument('--headless')
    
    service = Service(log_output=os.devnull, service_args=['--log', 'fatal'])
    driver = webdriver.Firefox(options=options, service=service)

    return driver

def create_auth_webdriver(url, session, headless=True):
    # Get cookies from requests.Session
    cookies = session.cookies.get_dict()

    options = webdriver.FirefoxOptions()

    # Add proxies if set
    if not session.proxies == {}:
        proxy = urlparse(session.proxies.get('http')).netloc
        proxy_host = proxy.split(':')[0]
        proxy_port = int(proxy.split(':')[1])

        options.set_preference("network.proxy.type", 1)
        options.set_preference("network.proxy.http", proxy_host)
        options.set_preference("network.proxy.http_port", proxy_port)
        options.set_preference("network.proxy.ssl", proxy_host)
        options.set_preference("network.proxy.ssl_port", proxy_port)
    
    # Ignore Cert Issues
    options.set_preference("network.captive-portal-service.enabled", False)
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--ignore-ssl-errors')
    options.add_argument('--disable-infobars')
    options.add_argument('--ignore-certificate-errors-spki-list')
    options.add_argument('--allow-running-insecure-content')
    options.add_argument('--disable-web-security')
    if headless:
        options.add_argument('--headless')
    
    service = Service(log_output=os.devnull, service_args=['--log', 'fatal'])
    driver = webdriver.Firefox(options=options, service=service)

    driver.get(url)

    for cookie in session.cookies:
        domain = urlparse(url).netloc
        driver.add_cookie({
            'name': cookie.name,
            'value': cookie.value,
            'domain': domain,
        })

    return driver

def get_rendered_content(url, driver):
    driver.get(url)
    driver.implicitly_wait(10)
    rendered_html = driver.page_source
    return rendered_html