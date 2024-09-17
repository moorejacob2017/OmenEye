## OmenEye v0.1 Beta

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
  --output OUTPUT       Required output DB name (Do not use an existing DB)
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


## Features

### Javascript Rendering
Many modern web pages use JavaScript to load content after the initial HTTP request, which can cause scrapers and crawlers relying on static analysis to miss important links and inputs. OmenEye addresses this by offering the option to use Selenium with GeckoDriver/Firefox, allowing full page rendering for a complete view before processing.

### Authenticated Crawling
Most critical attack surfaces lie behind authentication and are difficult for crawlers to reach. OmenEye includes a MITM proxy that intercepts web requests before the crawl, allowing it to use captured cookies for authentication and access those hard-to-reach areas.

### WAF Block Detection
OmenEye includes two types of canaries for detecting WAF blocks and adjusting the crawl accordingly. The **Basic Canary** establishes a baseline and periodically sends requests to detect changes in responses, signaling when a block occurs. The **Adaptive Canary** builds on this by adding a backoff mechanism that slows the crawl once a block is cleared, helping it stay below the block threshold.


### Sqlite Database Output
The crawl results are stored in an SQLite3 database, providing a versatile and lightweight format for data analysis. This database can be easily integrated with a wide range of tools to examine the crawl's outcome and further process the collected information. The database schema is as follows:

```
-----------------------[Output Database Schema]-----------------------
    CREATE TABLE responses (
        response_id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT,
        visited INTEGER,
        status_code INTEGER,
        body BLOB
    )

    CREATE TABLE headers (
        header_id INTEGER PRIMARY KEY AUTOINCREMENT,
        response_id INTEGER,
        header_name TEXT,
        header_value TEXT,
        FOREIGN KEY (response_id) REFERENCES responses(response_id)
    )

    CREATE TABLE links (
        link_id INTEGER PRIMARY KEY AUTOINCREMENT,
        response_id INTEGER,
        link TEXT,
        FOREIGN KEY (response_id) REFERENCES responses(response_id)
    )

    CREATE TABLE query_params (
        param_id INTEGER PRIMARY KEY AUTOINCREMENT,
        response_id INTEGER,
        param_name TEXT,
        param_value TEXT,
        FOREIGN KEY (response_id) REFERENCES responses(response_id)
    )

    CREATE TABLE inputs (
        input_id INTEGER PRIMARY KEY AUTOINCREMENT,
        response_id INTEGER,
        tag TEXT,
        tag_name TEXT,
        tag_value TEXT,
        FOREIGN KEY (response_id) REFERENCES responses(response_id)
    )
----------------------------------------------------------------------
```

