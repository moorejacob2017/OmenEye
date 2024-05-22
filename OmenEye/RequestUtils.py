import requests

try:
    import chardet
except ImportError:
    import charset_normalizer as chardet

from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode, urljoin, parse_qs

import gzip
import io
import re
from bs4 import BeautifulSoup
import feedparser

from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def standardize_url(url):
    # Parse the URL into components
    parsed_url = urlparse(url)
    
    # Convert scheme and netloc to lowercase
    scheme = parsed_url.scheme.lower()
    netloc = parsed_url.netloc.lower()
    
    # Handle default ports
    if (scheme == "http" and netloc.endswith(":80")):
        netloc = netloc[:-3]
    elif (scheme == "https" and netloc.endswith(":443")):
        netloc = netloc[:-4]
    
    # Sort query parameters
    query = parsed_url.query
    if query:
        query_params = parse_qsl(query)
        sorted_query = sorted(query_params)
        query = urlencode(sorted_query)
    
    # Rebuild the URL without trailing slashes for path
    path = parsed_url.path.rstrip('/')
    
    # Reconstruct the URL
    standardized_url = urlunparse((scheme, netloc, path, parsed_url.params, query, parsed_url.fragment))
    
    return standardized_url


def is_valid_url(url):
    # Regular expression to validate URLs
    url_regex = re.compile(
        r'^(?:http|ftp)s?://' # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' # domain...
        r'localhost|' # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|' # ...or ipv4
        r'\[?[A-F0-9]*:[A-F0-9:]+\]?)' # ...or ipv6
        r'(?::\d+)?' # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    return re.match(url_regex, url) is not None

def check_urls_list(text):
    # Split the text into lines
    lines = text.strip().split('\n')
    
    # Check each line to see if it's a valid URL
    for line in lines:
        if not is_valid_url(line.strip()):
            return False
    
    return True

def filter_invalid_urls(url_list):
    # Filter out invalid URLs
    valid_urls = [line.strip() for line in url_list if is_valid_url(line.strip())]
    return valid_urls


def get_content_with_max_size(response, max_size):
    total_size = 0
    content = b''  # Initialize an empty byte string to store the content
    for chunk in response.iter_content(chunk_size=1024):  # Adjust chunk size as needed
        total_size += len(chunk)
        content += chunk  # Append the chunk to the content
        if total_size > max_size:
            response.close()  # Close the connection
            raise ValueError("Response size exceeds maximum size")
    return content

def get_text(response, content):
    text = None
    encoding = response.encoding
    if not content:
        text = ""
    else:
        # Fallback to auto-detected encoding.
        if response.encoding is None:
            encoding = chardet.detect(content)["encoding"]
            #encoding = response.apparent_encoding

        try: # Decode unicode from given encoding.
            text = str(content, encoding, errors="replace")
        except (LookupError, TypeError):
            # A LookupError is raised if the encoding was not found which could
            # indicate a misspelling or similar mistake.
            #
            # A TypeError can be raised if encoding is None
            #
            # So we try blindly encoding.
            text = str(content, errors="replace")
    return text


def get_url(url):
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36 Edge/12.246'
    request = requests.Request('GET', url, headers={'User-Agent': user_agent})

    with requests.Session() as s:
        s.keep_alive = False
        prepped = s.prepare_request(request)
        retry_count = 0

        while retry_count <= 2:
            try:
                while True:
                    #https://stackoverflow.com/questions/10115126/python-requests-close-http-connection
                    response = s.send(prepped, stream=True, verify=False, allow_redirects=False, timeout=10)
                    content = get_content_with_max_size(response, max_size=1024*1024*250) # 250 MB
                    break
            except requests.RequestException as e:
                retry_count += 1
                response = None
                content = None
            else:
                break
        if response:
            response.close()

    return response, content


def get_url_w_request_and_session(request, session):
    prepped = session.prepare_request(request)

    retry_count = 0
    while retry_count <= 2:
        try:
            while True:
                #https://stackoverflow.com/questions/10115126/python-requests-close-http-connection
                response = session.send(prepped, stream=True, verify=False, allow_redirects=False, timeout=10)
                content = get_content_with_max_size(response, max_size=1024*1024*250) # 250 MB
                break
        except requests.RequestException as e:
            retry_count += 1
            response = None
            content = None
        else:
            break
    if response:
        response.close()

    return response, content

def is_gz_file(binary_content):
    # Check the magic number for gzip files (1f 8b)
    return binary_content[:2] == b'\x1f\x8b'

def unpack_gz_content(binary_content):
    if not is_gz_file(binary_content):
        return b""
    
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(binary_content)) as gz:
            unpacked_content = gz.read()
        return unpacked_content
    except (OSError, gzip.BadGzipFile):
        # Return empty bytes if there's an error during unpacking
        return b""

# Takes DummyResponse.response
def get_links(response, content):
    links = set()  # Using a set to avoid duplicate links
    soup = None
    parsed = urlparse(response.url)

    if response.is_redirect and 'Location' in response.headers:
        original_url = response.request.url
        location = response.headers['Location']
        full_url = urljoin(original_url, location)
        links.add(full_url)

    elif response.is_redirect and 'location' in response.headers:
        original_url = response.request.url
        location = response.headers['location']
        full_url = urljoin(original_url, location)


    if 'Content-Type' in response.headers:
        content_type = response.headers['Content-Type'].lower()
    elif 'content-type' in response.headers:
        content_type = response.headers['content-type'].lower()
    else:
        content_type = ''

    try:
        # RSS Feeds
        if parsed.path.endswith('.rss'):
            feed = feedparser.parse(response.url)
            for entry in feed.entries:
                links = entry.link
                full_url = urljoin(response.url, link)
                parsed_url = urlparse(full_url)
                if parsed_url.scheme and parsed_url.netloc:
                    links.add(full_url)
        
        elif 'xml' in content_type:
            soup = BeautifulSoup(get_text(response, content), 'xml')

        elif 'html' in content_type:
            soup = BeautifulSoup(get_text(response, content), 'html.parser')

        # For Plaintext Sitemaps
        elif 'text/plain' in content_type:
            if check_urls_list(get_text(response, content)):
                links.update(filter_invalid_urls(list(set(get_text(response, content).strip().split('\n')))))
            
        # For Sitemaps 
        elif parsed.path.endswith('.txt.gz') and is_gz_file(content):
            content = unpack_gz_content(content)
            text = str(content, errors="replace")
            if check_urls_list(text):
                links.update(filter_invalid_urls(list(set(text.strip().split('\n')))))
            
        elif parsed.path.endswith('.gz') and is_gz_file(content):
            content = unpack_gz_content(content)
            text = str(content, errors="replace")
            soup = BeautifulSoup(text, 'xml')

        if soup:
            # Define the tags and attributes to look for
            tags_attributes = {
                'a': 'href',
                'img': 'src',
                'link': 'href',
                'script': 'src',
                'source': ['src', 'srcset'],
                'video': 'src',
                'form': 'action',
                'iframe': 'src',
                'object': 'data',
                'embed': 'src',
                'audio': 'src',
                'base': 'href',
                'area': 'href',
                'input': 'src',
                'param': 'value',
                'blockquote': 'cite',
                'q': 'cite',
                'del': 'cite',
                'ins': 'cite',
                'track': 'src',
            }

            # Iterate over the defined tags and attributes and extract links
            for tag, attributes in tags_attributes.items():
                if not isinstance(attributes, list):
                    attributes = [attributes]
                for attribute in attributes:
                    for element in soup.find_all(tag, **{attribute: True}):
                        # Additional conditions for specific tags
                        #if tag == 'meta' and element.get('http-equiv', '').lower() == 'refresh':
                        #    continue
                        #if tag == 'input' and element.get('type', '').lower() != 'image':
                        #    continue
                        #if tag == 'param' and element.get('name', '').lower() != 'movie':
                        #    continue

                        link = element[attribute]
                        full_url = urljoin(response.url, link)

                        # Validate the URL
                        parsed_url = urlparse(full_url)
                        if parsed_url.scheme and parsed_url.netloc:
                            links.add(full_url)


            for element in soup.find_all(href=True):
                link = element['href']
                full_url = urljoin(response.url, link)

                # Validate the URL
                parsed_url = urlparse(full_url)
                if parsed_url.scheme and parsed_url.netloc:
                    links.add(full_url)

            for element in soup.find_all('loc'):
                link = element.get_text()
                full_url = urljoin(response.url, link)

                # Validate the URL
                parsed_url = urlparse(full_url)
                if parsed_url.scheme and parsed_url.netloc:
                    links.add(full_url)


    except Exception as e:
        print(f"An error occurred: {e}")

    return list(links)

def get_qps(url):
    qps = []
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    #print(query_params)
    for qp in query_params:
        qvs = query_params[qp]
        for qv in qvs:
            qps.append((qp, qv))
    return qps

def get_inputs(response, content):
    inputs = []

    if 'Content-Type' in response.headers:
        content_type = response.headers['Content-Type'].lower()
    elif 'content-type' in response.headers:
        content_type = response.headers['content-type'].lower()
    else:
        content_type = ''

    if 'html' in content_type:
        soup = BeautifulSoup(get_text(response, content), 'html.parser')
        
        # Query the tags: 'input', 'textarea', 'select', 'option', 'button', and 'datalist'
        elements = soup.select('input, textarea, select, option, button, datalist')
        inputs = []
        input_tags = []
        for element in elements:
            tag = str(element).split('>')[0] + '>'
            tag_name = element.get('name', '')
            tag_value = element.get('value', '')
            inputs.append((tag, tag_name, tag_value))
    return inputs


'''
class DummyResponse:
    def __init__(self, response=None, content=b''):
        self.visited = True
        self.status_code = int(response.status_code)
        self.content = bytes(content)
        self.headers = dict(response.headers)
        self.url = str(response.request.url)
        self.text = get_text(response, content)
        self.links = get_links(response, content)
        self.query_params = get_qps(self.url)
        self.inputs = get_inputs(response, content)
    
    @classmethod
    def blank_w_url(self, url):
        self.url = str(url)
        self.visited = True
        self.status_code = None
        self.content = None
        self.headers = {}
        self.text = None
        self.links = []
        self.query_params = []
        self.inputs = []

r, c = get_url('https://scrapeme.live/shop/')
r = DummyResponse(r, c)


print(get_qps('https://scrapeme.live/shop/?test=a&test='))
for l in r.links:
    #get_qps(l)
    print(get_qps(l))
'''