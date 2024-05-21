import re
import asyncio
import requests
import threading
import curses
from mitmproxy import ctx
from mitmproxy import options
from mitmproxy import http
from mitmproxy.tools.dump import DumpMaster

class InteractiveHTTPProxy:
    def __init__(self):
        self.session = requests.Session()
        self.user_input = None
        self.proxy_master = None

        self.found_auth = False
        self.auth_request = None

    def request(self, flow):
        if not self.found_auth:
            def print_request(stdscr, flow):
                stdscr.clear()
                stdscr.addstr("==============================================\n")
                stdscr.addstr(f"{flow.request.method} {flow.request.url} {flow.request.http_version}\n")
                for header, value in flow.request.headers.items():
                    stdscr.addstr(f"{header}: {value}\n")
                if flow.request.content:
                    stdscr.addstr("\n")
                    stdscr.addstr(flow.request.content.decode('utf-8') + "\n")
                stdscr.addstr("\n")
                stdscr.addstr("==============================================\n")
                stdscr.addstr("Use this request for authentication (y/n)? ")
                stdscr.refresh()

            def get_user_input(stdscr):
                while True:
                    print_request(stdscr, flow)
                    uin = stdscr.getkey()
                    if uin.strip().lower() == "y":
                        self.found_auth = True
                        url = flow.request.url
                        headers = flow.request.headers.copy()
                        data = flow.request.content.decode('utf-8') if flow.request.content else None
                        if data:
                            # If POST
                            self.auth_request = requests.Request(flow.request.method, url, headers=headers, data=data)
                        else:
                            # If GET
                            self.auth_request = requests.Request(flow.request.method, url, headers=headers)
                        
                        ctx.master.shutdown()
                        break
                    elif uin.strip().lower() == "n":
                        break

            curses.wrapper(lambda stdscr: get_user_input(stdscr))

    def start_proxy(self, port: int = 8080) -> None:
        async def _run():
            #quiet=True causes problems
            opts = options.Options(listen_host='0.0.0.0', listen_port=port)
            self.proxy_master = DumpMaster(opts)
            self.proxy_master.addons.add(self)
            await self.proxy_master.run()

        try:
            asyncio.run(_run())
        except Exception as e:
            print(f"Error occurred while running proxy: {e}")

    def done(self) -> None:
        self.session.close()


def get_auth_session(port=8080):
    interactive_proxy = InteractiveHTTPProxy()
    try:
        interactive_proxy.start_proxy(port)
        interactive_proxy.done()

        auth_request = interactive_proxy.auth_request
        
        if 'cookie' in auth_request.headers.keys():
            cookie_header = auth_request.headers.get('cookie')
        if 'Cookie' in auth_request.headers.keys():
            cookie_header = auth_request.headers.get('Cookie')
        if 'cookies' in auth_request.headers.keys():
            cookie_header = auth_request.headers.get('cookies')
        if 'Cookies' in auth_request.headers.keys():
            cookie_header = auth_request.headers.get('Cookies')
        # Split the cookie string using a regular expression to handle both commas and semicolons as separators

        cookie_parts = re.split(r';\s*|,\s*', cookie_header)
        # For each part, split by '=' to get the name and value of the cookie, and create a dictionary from the extracted name-value pairs
        cookie_dict = {c.split('=', 1)[0]: c.split('=', 1)[1] for c in cookie_parts if '=' in c}
        # Convert the dictionary to a RequestsCookieJar object
        cookies = requests.utils.cookiejar_from_dict(cookie_dict)

        #print(cookies)
        #input()

        session = requests.Session()

        session.cookies.update(cookies)
        prepped = session.prepare_request(auth_request)
        response = session.send(prepped, verify=False)

    except KeyboardInterrupt:
        #print("Mitmproxy is shutting down...")
        #ctx.master.shutdown()
        pass

    return session



'''
print("\033[1;34m[*] Mitmproxy is running...\033[0m")
s = get_auth_session(8080)
print('\033[1;32m[+] Redirecting HTTP flow from Browser to Crawler...\033[0m')

resp = requests.get("http://192.168.1.201:3000/profile")
print(resp.text)

print("==========================")

resp = s.get("http://192.168.1.201:3000/profile")
print(resp.text)
'''