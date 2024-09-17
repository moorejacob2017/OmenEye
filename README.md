## Omen Eye

A next-gen web crawler for precise attack surface mapping. Dumps results from a web crawl to an SQLite3 DB for easy analysis.


```txt
usage: omeneye [-h] --url URL --output OUTPUT [--seed-file SEED_FILE] [--mitm [PORT]] [--depth DEPTH]
               [--delay DELAY] [--jitter JITTER] [--robots] [--sitemaps] [--subdomains] [--js-grabbing]
               [--unvisited] [--silent] [--blacklist BLACKLIST] [--canary {basic,adaptive}] [--proxy HOST:PORT]
               [--render] [--no-headless] [--drivers NUM] [--builders NUM] [--workers NUM] [--parsers NUM]
               [--db-workers NUM]

Omen Eye - Specialty site mapper and web crawler

options:
  -h, --help            show this help message and exit
  --url URL             Required URL to crawl
  --output OUTPUT       Required output DB name (do not use an existing DB)
  --seed-file SEED_FILE
                        A list of urls to seed the crawl from
  --mitm [PORT]         MITM port for catching an authenticated request for authed crawls (Default 8080 if used)
  --depth DEPTH         Optional depth, defaults to 2 when not explicitly set
  --delay DELAY         Optional delay in seconds, requires an integer value
  --jitter JITTER       Add jitter to requests
  --robots              Flag to follow robots.txt. Defaults to False. (Only Allow/Disallow Directives)
  --sitemaps            Flag to seed with sitemaps. Defaults to False.
  --subdomains          Flag to include subdomains. Defaults to False.
  --js-grabbing         Flag to grab out of scope JS files. Defaults to False.
  --unvisited           Flag to include in-domain urls in the results that were seen, but were unvisited due to
                        scope or depth. Defaults to False.
  --silent              Flag to run without live curses output. Defaults to False.
  --blacklist BLACKLIST
                        A file with a list of blacklist regex to avoid when crawling
  --canary {basic,adaptive}
                        Use a basic or adaptive HTTP WAF Canary
  --proxy HOST:PORT     HTTP/S proxy to tunnel requests through
  --render              Flag to use Firefox/GeckoDriver to render dynamic webpages. Defaults to False. (Can be slow
                        and resource intensive)
  --no-headless         Wanna watch the Rendering Drivers work?
  --drivers NUM         Number of Rendering Drivers to use if rendering (Default 1) (WARNING: This number is doubled
                        whenever the render, auth, and subdomains args are used together)
  --builders NUM        Number of Request Builders (Default 1)
  --workers NUM         Number of Request Workers (Default 5)
  --parsers NUM         Number of Response Parsers (Default 2)
  --db-workers NUM      Number of DB Workers (Default 3)
```


