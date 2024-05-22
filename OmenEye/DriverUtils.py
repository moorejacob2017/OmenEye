import os
from selenium import webdriver
from urllib.parse import urlparse

def create_webdriver(url, session):
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
    options.add_argument('--headless')
    #options.set_preference("general.useragent.override", "whatever_useragent") No working

    #driver = webdriver.Firefox(options=options)
    driver = webdriver.Firefox(options=options, service_log_path=os.devnull)

    return driver

def create_auth_webdriver(url, session):
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
    options.add_argument('--headless')
    #options.set_preference("general.useragent.override", "whatever_useragent") No working

    #driver = webdriver.Firefox(options=options)
    driver = webdriver.Firefox(options=options, service_log_path=os.devnull)
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