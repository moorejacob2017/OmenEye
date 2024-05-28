import base64
import glob
import gzip
import http.client
import http.server
import importlib
import json
import os
import re
import select
import socket
import ssl
import sys
import threading
import time
import urllib.parse
import zlib
from http.client import HTTPMessage
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from subprocess import PIPE, Popen

import requests
import curses

'''
RED = 31
GREEN = 32
YELLOW = 33
BLUE = 34
MAGENTA = 35
CYAN = 36


def with_color(c: int, s: str):
    return "\x1b[%dm%s\x1b[0m" % (c, s)
'''

# Define the ANSI color codes
RED = 31
GREEN = 32
YELLOW = 33
BLUE = 34
MAGENTA = 35
CYAN = 36

# Mock function to emulate with_color behavior for curses
def with_color(stdscr, color_pair, text):
    stdscr.addstr(text, curses.color_pair(color_pair))
    stdscr.addstr("\n")


def wrap_text(text, width):
    lines = []
    for line in text.splitlines():
        while len(line) > width:
            lines.append(line[:width])
            line = line[width:]
        lines.append(line)
    return lines


class Result:
    def __init__(self):
        self.result = None
        self.lock = threading.Lock()
    def set_result(self, item):
        if self.result == None:
            with self.lock:
                self.result = item



class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    address_family = socket.AF_INET6
    daemon_threads = True

    def handle_error(self, request, client_address):
        # surpress socket/ssl related errors
        cls, e = sys.exc_info()[:2]
        if cls is socket.error or cls is ssl.SSLError:
            pass
        else:
            return HTTPServer.handle_error(self, request, client_address)


class ProxyRequestHandler(BaseHTTPRequestHandler):
    lock = threading.Lock()

    def __init__(self, *args, **kwargs):
        self.tls = threading.local()
        self.tls.conns = {}

        super().__init__(*args, **kwargs)

    def log_error(self, format, *args):
        # surpress "Request timed out: timeout('timed out',)"
        if isinstance(args[0], socket.timeout):
            return

        self.log_message(format, *args)

    def do_CONNECT(self):
        host, _ = self.path.split(":", 1)
        # if args.userpass:
        #     auth = self.headers.get("Proxy-Authorization")
        #     print("Proxy-Authorization: ", dict(self.headers.items()))
        #     if not auth:
        #         print("Client does not provide userpass as '%s'" % args.userpass)
        #         self.send_header("Proxy-Authenticate", 'Basic realm="%s"' % host)
        #         self.send_error(407)
        #         return
        #     client_userpass = base64.b64decode(auth[6:])
        #     if args.userpass != client_userpass:
        #         print("Client userpass '%s' != '%s'" % (client_userpass, args.userpass))
        #         self.send_error(403)
        #         return

        # print("args.domain", args.domain, "host", host, "equal", args.domain == host)
        if (
            os.path.isfile(oe_ca_key)
            and os.path.isfile(oe_ca_cert)
            and os.path.isfile(oe_cert_key)
            and os.path.isdir(oe_cert_dir)
            and (oe_domain == "*" or oe_domain == host)
        ):
            #print("HTTPS mitm enabled, Intercepting...")
            self.connect_intercept()
        else:
            #print("HTTPS relay only, NOT Intercepting...")
            self.connect_relay()

    def connect_intercept(self):
        hostname = self.path.split(":")[0]
        certpath = os.path.join(oe_cert_dir, hostname + ".pem")
        confpath = os.path.join(oe_cert_dir, hostname + ".conf")

        with self.lock:
            # stupid requirements from Apple: https://support.apple.com/en-us/HT210176
            if not os.path.isfile(certpath):
                if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", hostname):
                    category = "IP"
                else:
                    category = "DNS"
                with open(confpath, "w") as f:
                    f.write(
                        "subjectAltName=%s:%s\nextendedKeyUsage=serverAuth\n"
                        % (category, hostname)
                    )
                epoch = "%d" % (time.time() * 1000)
                # CSR
                p1 = Popen(
                    [
                        "openssl",
                        "req",
                        "-sha256",
                        "-new",
                        "-key",
                        oe_cert_key,
                        "-subj",
                        "/CN=%s" % hostname,
                        "-addext",
                        "subjectAltName=DNS:%s" % hostname,
                    ],
                    stdout=PIPE,
                )
                # Sign
                p2 = Popen(
                    [
                        "openssl",
                        "x509",
                        "-req",
                        "-sha256",
                        "-days",
                        "365",
                        "-CA",
                        oe_ca_cert,
                        "-CAkey",
                        oe_ca_key,
                        "-set_serial",
                        epoch,
                        "-out",
                        certpath,
                        "-extfile",
                        confpath,
                    ],
                    stdin=p1.stdout,
                    stderr=PIPE,
                )
                p2.communicate()

        self.send_response(200, "Connection Established")
        self.end_headers()

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.verify_mode = ssl.CERT_NONE
        # print(args.cert_key)
        context.load_cert_chain(certpath, oe_cert_key)
        try:
            self.connection = context.wrap_socket(self.connection, server_side=True)
        except ssl.SSLEOFError:
            #print("Handshake refused by client, maybe SSL pinning?")
            return
        self.rfile = self.connection.makefile("rb", self.rbufsize)
        self.wfile = self.connection.makefile("wb", self.wbufsize)

        conntype = self.headers.get("Proxy-Connection", "")
        if self.protocol_version == "HTTP/1.1" and conntype.lower() != "close":
            self.close_connection = False
        else:
            self.close_connection = True

    def connect_relay(self):
        address = self.path.split(":", 1)
        address = (address[0], int(address[1]) or 443)
        try:
            s = socket.create_connection(address, timeout=self.timeout)
        except curses._curses.error as e:
            print(f'Curses Error Caught: {e}')
            print('\n Try making your terminal screen bigger.')
        except Exception as e:
            return
        self.send_response(200, "Connection Established")
        self.end_headers()

        conns = [self.connection, s]
        self.close_connection = False
        while not self.close_connection:
            rlist, wlist, xlist = select.select(conns, [], conns, self.timeout)
            if xlist or not rlist:
                break
            for r in rlist:
                other = conns[1] if r is conns[0] else conns[0]
                data = r.recv(8192)
                if not data:
                    self.close_connection = True
                    break
                other.sendall(data)

    def do_GET(self):
        if self.path == "http://omeneye/":
            self.send_cacert()
            return

        req = self
        content_length = int(req.headers.get("Content-Length", 0))
        req_body = self.rfile.read(content_length) if content_length else b""

        if req.path[0] == "/":
            if isinstance(self.connection, ssl.SSLSocket):
                req.path = "https://%s%s" % (req.headers["Host"], req.path)
            else:
                req.path = "http://%s%s" % (req.headers["Host"], req.path)

        if request_handler is not None:
            # convert to str and back to bytes
            req_body_modified = request_handler(req, req_body.decode())
            if req_body_modified is False:
                self.send_error(403)
                return
            if req_body_modified is not None:
                req_body = req_body_modified.encode()
                req.headers["Content-Length"] = str(len(req_body))

        u = urllib.parse.urlsplit(req.path)
        scheme = u.scheme
        netloc = u.netloc
        path = u.path + "?" + u.query if u.query else u.path
        assert scheme in ("http", "https")
        if netloc:
            req.headers["Host"] = netloc
        req.headers = self.filter_headers(req.headers)  # type: ignore

        origin = (scheme, netloc)
        try:
            if origin not in self.tls.conns:
                if scheme == "https":
                    self.tls.conns[origin] = http.client.HTTPSConnection(
                        netloc, timeout=self.timeout
                    )
                else:
                    self.tls.conns[origin] = http.client.HTTPConnection(
                        netloc, timeout=self.timeout
                    )
            conn = self.tls.conns[origin]
            conn.request(self.command, path, req_body, dict(req.headers))
            res = conn.getresponse()

            # support streaming
            cache_control = res.headers.get("Cache-Control", "")
            if "Content-Length" not in res.headers and "no-store" in cache_control:
                if response_handler is not None:
                    response_handler(req, req_body, res, "")
                res.headers = self.filter_headers(res.headers)
                self.relay_streaming(res)
                if save_handler is not None:
                    with self.lock:
                        #save_handler(req, req_body, res, "")
                        #-------------------------------------------------------------------------
                        if not caught_request.result:
                            if curses.wrapper(save_handler, req, req_body, res, ""):
                                print("Processing the request and shutting down the server.")
                                threading.Thread(target=self.server.shutdown).start()
                                caught_request.set_result(req.headers)
                        #-------------------------------------------------------------------------
                return

            res_body = res.read()
        except curses._curses.error as e:
            print(f'Curses Error Caught: {e}')
            print('\n Try making your terminal screen bigger.')
        except Exception as e:
            if origin in self.tls.conns:
                del self.tls.conns[origin]
            self.send_error(502)
            return

        if response_handler is not None:
            content_encoding = res.headers.get("Content-Encoding", "identity")
            res_body_plain = self.decode_content_body(res_body, content_encoding)
            res_body_modified = response_handler(req, req_body, res, res_body_plain)
            if res_body_modified is False:
                self.send_error(403)
                return
            if res_body_modified is not None:
                res_body = self.encode_content_body(res_body_modified, content_encoding)
                res.headers["Content-Length"] = str(len(res_body))

        res.headers = self.filter_headers(res.headers)

        self.send_response_only(res.status, res.reason)
        for k, v in res.headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(res_body)
        self.wfile.flush()

        if save_handler is not None:
            content_encoding = res.headers.get("Content-Encoding", "identity")
            res_body_plain = self.decode_content_body(res_body, content_encoding)
            with self.lock:
                #save_handler(req, req_body, res, res_body_plain)
                #-------------------------------------------------------------------------
                if not caught_request.result:
                    if curses.wrapper(save_handler, req, req_body, res, res_body_plain):
                        print("Processing the request and shutting down the server.")
                        threading.Thread(target=self.server.shutdown).start()
                        caught_request.set_result(req.headers)
                #-------------------------------------------------------------------------

    def relay_streaming(self, res):
        self.send_response_only(res.status, res.reason)
        for k, v in res.headers.items():
            self.send_header(k, v)
        self.end_headers()
        try:
            while True:
                chunk = res.read(8192)
                if not chunk:
                    break
                self.wfile.write(chunk)
            self.wfile.flush()
        except socket.error:
            # connection closed by client
            pass

    do_HEAD = do_GET
    do_POST = do_GET
    do_PUT = do_GET
    do_DELETE = do_GET
    do_OPTIONS = do_GET

    def filter_headers(self, headers: HTTPMessage) -> HTTPMessage:
        # http://tools.ietf.org/html/rfc2616#section-13.5.1
        hop_by_hop = (
            "connection",
            "keep-alive",
            "proxy-authenticate",
            "proxy-authorization",
            "te",
            "trailers",
            "transfer-encoding",
            "upgrade",
        )
        for k in hop_by_hop:
            del headers[k]

        # accept only supported encodings
        if "Accept-Encoding" in headers:
            ae = headers["Accept-Encoding"]
            filtered_encodings = [
                x
                for x in re.split(r",\s*", ae)
                if x in ("identity", "gzip", "x-gzip", "deflate")
            ]
            headers["Accept-Encoding"] = ", ".join(filtered_encodings)

        return headers

    def encode_content_body(self, text: bytes, encoding: str) -> bytes:
        if encoding == "identity":
            data = text
        elif encoding in ("gzip", "x-gzip"):
            data = gzip.compress(text)
        elif encoding == "deflate":
            data = zlib.compress(text)
        else:
            raise Exception("Unknown Content-Encoding: %s" % encoding)
        return data

    def decode_content_body(self, data: bytes, encoding: str) -> bytes:
        if encoding == "identity":
            text = data
        elif encoding in ("gzip", "x-gzip"):
            text = gzip.decompress(data)
        elif encoding == "deflate":
            try:
                text = zlib.decompress(data)
            except zlib.error:
                text = zlib.decompress(data, -zlib.MAX_WBITS)
        else:
            raise Exception("Unknown Content-Encoding: %s" % encoding)
        return text

    def send_cacert(self):
        with open(oe_ca_cert, "rb") as f:
            data = f.read()

        self.send_response(200, "OK")
        self.send_header("Content-Type", "application/x-x509-ca-cert")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)


def parse_qsl(s):
    return "\n".join(
        "%-20s %s" % (k, v)
        for k, v in urllib.parse.parse_qsl(s, keep_blank_values=True)
    )


'''
def print_info(req, req_body, res, res_body):
    req_header_text = "%s %s %s\n%s" % (
        req.command,
        req.path,
        req.request_version,
        req.headers,
    )
    version_table = {10: "HTTP/1.0", 11: "HTTP/1.1"}
    res_header_text = "%s %d %s\n%s" % (
        version_table[res.version],
        res.status,
        res.reason,
        res.headers,
    )

    print(with_color(YELLOW, req_header_text))

    u = urllib.parse.urlsplit(req.path)
    if u.query:
        query_text = parse_qsl(u.query)
        print(with_color(GREEN, "==== QUERY PARAMETERS ====\n%s\n" % query_text))

    cookie = req.headers.get("Cookie", "")
    if cookie:
        cookie = parse_qsl(re.sub(r";\s*", "&", cookie))
        print(with_color(GREEN, "==== COOKIE ====\n%s\n" % cookie))

    auth = req.headers.get("Authorization", "")
    if auth.lower().startswith("basic"):
        token = auth.split()[1].decode("base64")
        print(with_color(RED, "==== BASIC AUTH ====\n%s\n" % token))

    if req_body is not None:
        req_body_text = None
        content_type = req.headers.get("Content-Type", "")

        if content_type.startswith("application/x-www-form-urlencoded"):
            req_body_text = parse_qsl(req_body)
        elif content_type.startswith("application/json"):
            try:
                json_obj = json.loads(req_body)
                json_str = json.dumps(json_obj, indent=2)
                if json_str.count("\n") < 50:
                    req_body_text = json_str
                else:
                    lines = json_str.splitlines()
                    req_body_text = "%s\n(%d lines)" % (
                        "\n".join(lines[:50]),
                        len(lines),
                    )
            except ValueError:
                req_body_text = req_body
        elif len(req_body) < 1024:
            req_body_text = req_body

        if req_body_text:
            print(with_color(GREEN, "==== REQUEST BODY ====\n%s\n" % req_body_text))

    print(with_color(CYAN, res_header_text))

    cookies = res.headers.get("Set-Cookie")
    if cookies:
        print(with_color(RED, "==== SET-COOKIE ====\n%s\n" % cookies))

    if res_body is not None:
        res_body_text = None
        content_type = res.headers.get("Content-Type", "")

        if content_type.startswith("application/json"):
            try:
                json_obj = json.loads(res_body)
                json_str = json.dumps(json_obj, indent=2)
                if json_str.count("\n") < 50:
                    res_body_text = json_str
                else:
                    lines = json_str.splitlines()
                    res_body_text = "%s\n(%d lines)" % (
                        "\n".join(lines[:50]),
                        len(lines),
                    )
            except ValueError:
                res_body_text = res_body
        elif content_type.startswith("text/html"):
            m = re.search(r"<title[^>]*>\s*([^<]+?)\s*</title>", res_body, re.I)
            if m:
                print(
                    with_color(
                        GREEN, "==== HTML TITLE ====\n%s\n" % m.group(1).decode()
                    )
                )
        elif content_type.startswith("text/") and len(res_body) < 1024:
            res_body_text = res_body

        if res_body_text:
            print(with_color(GREEN, "==== RESPONSE BODY ====\n%s\n" % res_body_text))

    #def prompt_user(self, save_handler, req, req_body, res, res_body_plain):
    while True:
        response = input("Do you want to use this request? (y/n): ").strip().lower()
        print()
        if response in ("y", "n"):
            return response == "y"
        print("Please enter 'y' or 'n'.")



def main():
    """place holder, no action, but do not delete."""


parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("-b", "--bind", default="localhost", help="Host to bind")
parser.add_argument("-p", "--port", type=int, default=8080, help="Port to bind")
parser.add_argument(
    "-d",
    "--domain",
    default="*",
    help="Domain to intercept, if not set, intercept all.",
)
parser.add_argument(
    "-u",
    "--userpass",
    help="Username and password for proxy authentication, format: 'user:pass'",
)
parser.add_argument("--timeout", type=int, default=5, help="Timeout")
parser.add_argument("--ca-key", default="./ca-key.pem", help="CA key file")
parser.add_argument("--ca-cert", default="./ca-cert.pem", help="CA cert file")
parser.add_argument("--cert-key", default="./cert-key.pem", help="site cert key file")
parser.add_argument("--cert-dir", default="./certs", help="Site certs files")
parser.add_argument(
    "--request-handler",
    help="Request handler function, example: foo.bar:handle_request",
)
parser.add_argument(
    "--response-handler",
    help="Response handler function, example: foo.bar:handle_response",
)
parser.add_argument(
    "--save-handler",
    help="Save handler function, use 'off' to turn off, example: foo.bar:handle_save",
)
parser.add_argument(
    "--make-certs", action="store_true", help="Create https intercept certs"
)
parser.add_argument(
    "--make-example",
    action="store_true",
    help="Create an intercept handlers example python file",
)
args = parser.parse_args()

if args.make_certs:
    Popen(["openssl", "genrsa", "-out", args.ca_key, "2048"]).communicate()
    Popen(
        [
            "openssl",
            "req",
            "-new",
            "-x509",
            "-days",
            "3650",
            "-key",
            args.ca_key,
            "-sha256",
            "-out",
            args.ca_cert,
            "-subj",
            "/CN=Proxy3 CA",
        ]
    ).communicate()
    Popen(["openssl", "genrsa", "-out", args.cert_key, "2048"]).communicate()
    os.makedirs(args.cert_dir, exist_ok=True)
    for old_cert in glob.glob(os.path.join(args.cert_dir, "*.pem")):
        os.remove(old_cert)
    sys.exit(0)

if args.make_example:
    import shutil

    example_file = os.path.join(os.path.dirname(__file__), "examples/example.py")
    shutil.copy(example_file, "proxy3_handlers_example.py")
    sys.exit(0)

if args.request_handler:
    module, func = args.request_handler.split(":")
    m = importlib.import_module(module)
    request_handler = getattr(m, func)
else:
    request_handler = None
if args.response_handler:
    module, func = args.response_handler.split(":")
    m = importlib.import_module(module)
    response_handler = getattr(m, func)
else:
    response_handler = None
if args.save_handler:
    if args.save_handler == "off":
        save_handler = None
    else:
        module, func = args.save_handler.split(":")
        m = importlib.import_module(module)
        save_handler = getattr(m, func)
else:
    save_handler = print_info

protocol = "HTTP/1.1"
http.server.test(
    HandlerClass=ProxyRequestHandler,
    ServerClass=ThreadingHTTPServer,
    protocol=protocol,
    port=args.port,
    bind=args.bind,
)
'''
def print_info(stdscr, req, req_body, res, res_body):
    curses.start_color()
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)

    stdscr.clear()

    req_header_text = "%s %s %s\n%s" % (
        req.command,
        req.path,
        req.request_version,
        req.headers,
    )
    version_table = {10: "HTTP/1.0", 11: "HTTP/1.1"}
    res_header_text = "%s %d %s\n%s" % (
        version_table[res.version],
        res.status,
        res.reason,
        res.headers,
    )

    content_lines = []

    content_lines.extend(wrap_text(req_header_text, curses.COLS))

    cookie = req.headers.get("Cookie", "")
    if cookie:
        cookie = parse_qsl(re.sub(r";\s*", "&", cookie))
        content_lines.append("====[ COOKIES ]====\n" )
        content_lines.extend(wrap_text(cookie, curses.COLS))

    if req_body is not None:
        try:
            req_body_text = None
            content_type = req.headers.get("Content-Type", "")

            if content_type.startswith("application/x-www-form-urlencoded"):
                req_body_text = parse_qsl(req_body)
            elif content_type.startswith("application/json"):
                try:
                    json_obj = json.loads(req_body)
                    json_str = json.dumps(json_obj, indent=2)
                    if json_str.count("\n") < 50:
                        req_body_text = json_str
                    else:
                        lines = json_str.splitlines()
                        req_body_text = "%s\n(%d lines)" % (
                            "\n".join(lines[:50]),
                            len(lines),
                        )
                except ValueError:
                    req_body_text = req_body
            elif len(req_body) < 1024:
                req_body_text = req_body
        except Exception as e:
            req_body_text = None

        if req_body_text:
            content_lines.append("====[ REQUEST BODY ]====")
            content_lines.extend(wrap_text(req_body_text, curses.COLS))

    # Displaying the content with scrolling
    max_y, max_x = stdscr.getmaxyx()
    pos = 0

    '''
    while True:
        stdscr.clear()
        for i in range(pos, min(pos + max_y - 3, len(content_lines))):
            stdscr.addstr(i - pos, 0, content_lines[i])
        stdscr.addstr(max_y - 2, 0, "Use UP/DOWN to scroll, Enter to confirm.")
        stdscr.refresh()

        key = stdscr.getch()
        if key == curses.KEY_UP and pos > 0:
            pos -= 1
        elif key == curses.KEY_DOWN and pos < len(content_lines) - (max_y - 3):
            pos += 1
        elif key == curses.KEY_ENTER or key in [10, 13]:
            break
    '''

    # Handling user prompt
    curses.echo()
    while True:
        stdscr.clear()
        for i in range(pos, min(pos + max_y - 3, len(content_lines))):
            stdscr.addstr(i - pos, 0, content_lines[i])
        stdscr.addstr(max_y - 2, 0, "Use UP/DOWN to scroll, Enter to confirm.")
        stdscr.addstr(max_y - 1, 0, "Do you want to use this request? (y/n): ")


        stdscr.clrtoeol()
        stdscr.refresh()

        key = stdscr.getch()

        if key == curses.KEY_UP and pos > 0:
            pos -= 1
        elif key == curses.KEY_DOWN and pos < len(content_lines) - (max_y - 3):
            pos += 1
        #elif key == curses.KEY_ENTER or key in [10, 13]:
        #    break
        #response = stdscr.getstr().strip().decode('utf-8').lower()

        if key in (121, 110):
            curses.noecho()
            # 121 == curses.keys 'y'
            return key == 121
        stdscr.addstr(max_y - 1, 0, "Invalid Key. Do you want to use this request? (y/n): ")
        stdscr.clrtoeol()
        stdscr.refresh()



def generate_certificates():
    global oe_ca_key
    global oe_ca_cert
    global oe_cert_key
    global oe_cert_dir
    global oe_domain

    home_directory = os.path.expanduser('~')
    oe_dir = f"{home_directory}/.omeneye"
    oe_ca_key = f"{oe_dir}/omeneye_ca-key.pem"
    oe_ca_cert = f"{oe_dir}/omeneye_ca-cert.pem"
    oe_cert_key = f"{oe_dir}/omeneye_cert-key.pem"
    oe_cert_dir = f"{oe_dir}/certs"
    oe_domain = "*"

    os.makedirs(oe_dir, exist_ok=True)

    # Make Cert and Key files
    if not os.path.exists(oe_ca_key):
        Popen(["openssl", "genrsa", "-out", oe_ca_key, "2048"]).communicate()
    if not os.path.exists(oe_ca_cert):
        Popen(
            [
                "openssl",
                "req",
                "-new",
                "-x509",
                "-days",
                "3650",
                "-key",
                oe_ca_key,
                "-sha256",
                "-out",
                oe_ca_cert,
                "-subj",
                "/CN=OmenEye CA",
            ]
        ).communicate()
    if not os.path.exists(oe_cert_key):
        Popen(["openssl", "genrsa", "-out", oe_cert_key, "2048"]).communicate()

    os.makedirs(oe_cert_dir, exist_ok=True)
    for old_cert in glob.glob(os.path.join(oe_cert_dir, "*.pem")):
        os.remove(old_cert)


def get_auth_session(port=8080):

    generate_certificates()

    print('')
    print(f'MITM proxy will be started on port {port}.')
    print(f'For HTTPS interception, install the Omen Eye Root CA Certificate located at {oe_ca_cert} or navigate to \'http://omeneye\' while using the MITM proxy to download it.')
    print('')

    global caught_request
    global save_handler
    global request_handler
    global response_handler

    caught_request = Result()
    save_handler = print_info
    request_handler = None
    response_handler = None

    protocol = "HTTP/1.1"
    http.server.test(
        HandlerClass=ProxyRequestHandler,
        ServerClass=ThreadingHTTPServer,
        protocol=protocol,
        port=port,
        bind='0.0.0.0',
    )

    headers = caught_request.result

    if 'cookie' in headers.keys():
        cookie_header = headers.get('cookie')
    if 'Cookie' in headers.keys():
        cookie_header = headers.get('Cookie')
    if 'cookies' in headers.keys():
        cookie_header = headers.get('cookies')
    if 'Cookies' in headers.keys():
        cookie_header = headers.get('Cookies')

    cookie_parts = re.split(r';\s*|,\s*', cookie_header)
    # For each part, split by '=' to get the name and value of the cookie, and create a dictionary from the extracted name-value pairs
    cookie_dict = {c.split('=', 1)[0]: c.split('=', 1)[1] for c in cookie_parts if '=' in c}
    # Convert the dictionary to a RequestsCookieJar object
    cookies = requests.utils.cookiejar_from_dict(cookie_dict)
    session = requests.Session()
    session.cookies.update(cookies)

    return session