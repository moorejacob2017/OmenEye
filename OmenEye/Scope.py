import re
from urllib.parse import urlparse, urlunparse
from .RequestUtils import *
#from .RequestUtils import get_url

class RobotsTxtParser:
    def __init__(self, url):
        self.blacklist_rules = []
        self.whitelist_rules = []
        self.sitemaps = []
        
        parsed_url = urlparse(url)
        if not parsed_url.path.endswith('/robots.txt'):
            path = '/robots.txt'
            url = urlunparse((parsed_url.scheme, parsed_url.netloc, path, '', '', ''))
        self.url = url
        self.get_robots()

    def get_robots(self):
        response, content = get_url(self.url)
        text = get_text(response, content)
        if text:
            try:
                self.parse(text)
            except:
                pass
    
    def parse(self, content):
        lines = content.splitlines()
        current_user_agent = None

        for line in lines:
            # Remove comments
            line = line.split('#', 1)[0].strip()
            if not line:
                continue
            
            parts = line.split(':', 1)
            field = parts[0].strip().lower()
            value = parts[1].strip() if len(parts) > 1 else ''

            if field == 'user-agent':
                current_user_agent = value
            if current_user_agent == '*':
                if field == 'disallow':
                    #self.rules.append((current_user_agent, 'disallow', self._parse_pattern(value)))
                    self.blacklist_rules.append(self._parse_pattern(value))
                elif field == 'allow':
                    #self.rules.append((current_user_agent, 'allow', self._parse_pattern(value)))
                    self.whitelist_rules.append(self._parse_pattern(value))
            if field == 'sitemap':
                self.sitemaps.append(value)
    
    def _parse_pattern(self, pattern):
        # Escape special characters except for wildcards
        escaped_pattern = re.escape(pattern)
        # Replace wildcard '*' with regular expression equivalent '.*'
        escaped_pattern = escaped_pattern.replace(r'\*', '.*')
        escaped_pattern = escaped_pattern.replace(r'\^', '^')
        escaped_pattern = escaped_pattern.replace(r'\$', '$')

        if not escaped_pattern == '' and escaped_pattern[-1] == '/':
            escaped_pattern += '[^?]*'

        return re.compile(escaped_pattern)


class Scope:
    def __init__(self, url, subdomains=False, js_grabbing=False):
        self.blacklist_rules = []
        self.whitelist_rules = []
        self.sitemaps = []
        self.subdomains = subdomains
        self.js_grabbing = js_grabbing
        self.url = url

        parsed = urlparse(url)
        netloc = parsed.netloc
        netloc = re.sub(r'^www\.', '', netloc)

        self.domain_pattern = re.escape(netloc) + r'$'

    def get_sitemaps_from_robots(self):
        robo = RobotsTxtParser(self.url)
        self.sitemaps += robo.sitemaps
        return robo.sitemaps

    def add_rules_from_robots(self):
        robo = RobotsTxtParser(self.url)
        self.blacklist_rules += robo.blacklist_rules
        self.whitelist_rules += robo.whitelist_rules

    def add_blacklist_rule(self, rule):
        self.blacklist_rules.append(re.compile(rule))
    
    def add_whitelist_rule(self, rule):
        self.whitelist_rules.append(re.compile(rule))

    def add_blacklist_rules_from_file(self, file):
        with open(file, 'r') as rf:
            rules = rf.read().strip().split('\n')
        for rule in rules:
            if not rule.strip() == '':
                self.add_blacklist_rule(rule.strip())

    def add_whitelist_rules_from_file(self, file):
        with open(file, 'r') as rf:
            rules = rf.read().strip().split('\n')
        for rule in rules:
            if not rule.strip() == '':
                self.add_whitelist_rule(rule.strip())

    def in_scope(self, url):
        parsed = urlparse(url)
        netloc = parsed.netloc
        netloc = re.sub(r'^www\.', '', netloc)

        # If Out-of-Scope JS Grabbing is allowed
        if self.js_grabbing:
            if parsed.path.endswith('.js'):
                return True

        if self.subdomains:
            if not re.search(self.domain_pattern, netloc):
                return False
        else:
            if not re.search(r'^' + self.domain_pattern, netloc):
                return False

        for pattern in self.whitelist_rules:
            if pattern.match(url):
                return True
        for pattern in self.blacklist_rules:
            if pattern.match(url):
                return False
        return True
    
    def in_domain(self, url):
        parsed = urlparse(url)
        netloc = parsed.netloc
        netloc = re.sub(r'^www\.', '', netloc)

        if re.search(self.domain_pattern, netloc):
            return True
        return False
