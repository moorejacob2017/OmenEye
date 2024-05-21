## Omen Eye

A next-gen web crawler for precision attack surface mapping. Dumps results from a web crawl out to an SQLite3 DB file for easy analysis.


```txt
usage: omeneye [-h] --url URL --output OUTPUT [--seed-file SEED_FILE] [--mitm [MITM]] [--depth DEPTH]
               [--delay DELAY] [--jitter JITTER] [--robots] [--sitemaps] [--subdomains] [--js-grabbing]
               [--unvisited] [--silent] [--blacklist-file BLACKLIST_FILE] [--canary {basic,adaptive}]
               [--proxy PROXY] [--builders BUILDERS] [--workers WORKERS] [--parsers PARSERS]
               [--db-workers DB_WORKERS]

Omen Eye - Specialty site mapper and web crawler

options:
  -h, --help            show this help message and exit
  --url URL             Required URL to crawl
  --output OUTPUT       Required output DB name (do not use an existing DB)
  --seed-file SEED_FILE
                        A list of urls to seed the crawl from
  --mitm [MITM]         MITM port for catching an authenticated request for authed crawls (Default 8080 if used)
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
  --blacklist-file BLACKLIST_FILE
                        A list of blacklist regex to avoid when crawling
  --canary {basic,adaptive}
                        Use a basic or adaptive HTTP WAF Canary
  --proxy PROXY         HTTP/S proxy to tunnel requests through (host:port)
  --builders BUILDERS   Number of Request Builders (Default 1)
  --workers WORKERS     Number of Request Workers (Default 5)
  --parsers PARSERS     Number of Response Parsers (Default 2)
  --db-workers DB_WORKERS
                        Number of DB Workers (Default 3)

TIP: You can use the sqlite3 cli tool to run queries from the command line
    Example: sqlite3 output.db 'SELECT url FROM responses'

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