import argparse
from OmenEye import OmenEye


def cli():
    parser = argparse.ArgumentParser(
        description='Omen Eye - Specialty site mapper and web crawler',
        #epilog=schema_text,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--url',
        type=str,
        required=True,  # The argument is required
        help='Required URL to crawl'
    )
    parser.add_argument(
        '--output',
        type=str,
        required=True,  # The argument is required
        help='Required output DB name (do not use an existing DB)'
    )
    parser.add_argument(
        '--seed-file',
        type=str,
        required=False, 
        help='A list of urls to seed the crawl from'
    )
    

    parser.add_argument(
        '--mitm',
        nargs='?',
        const=8080,  # Default value if the argument is provided without a value
        type=int,  # Specify that the argument should be an integer
        help='MITM port for catching an authenticated request for authed crawls (Default 8080 if used)',
        metavar='PORT'
    )
    parser.add_argument(
        '--depth',
        type=int,
        default=2,  # Default value if the argument is not provided
        help='Optional depth, defaults to 2 when not explicitly set'
    )
    parser.add_argument(
        '--delay',
        type=float,
        required=False,  # The argument is optional, but if provided, it must be an int
        help='Optional delay in seconds, requires an integer value'
    )
    parser.add_argument(
        '--jitter',
        type=float,
        required=False,  # The argument is optional, but if provided, it must be an int
        help='Add jitter to requests'
    )


    parser.add_argument(
        '--robots',
        action='store_true',  # The argument will be True if provided, False if not
        help='Flag to follow robots.txt. Defaults to False. (Only Allow/Disallow Directives)'
    )
    parser.add_argument(
        '--sitemaps',
        action='store_true',  # The argument will be True if provided, False if not
        help='Flag to seed with sitemaps. Defaults to False.'
    )
    parser.add_argument(
        '--subdomains',
        action='store_true',  # The argument will be True if provided, False if not
        help='Flag to include subdomains. Defaults to False.'
    )
    parser.add_argument(
        '--js-grabbing',
        action='store_true',  # The argument will be True if provided, False if not
        help='Flag to grab out of scope JS files. Defaults to False.'
    )
    parser.add_argument(
        '--unvisited',
        action='store_true',  # The argument will be True if provided, False if not
        help='Flag to include in-domain urls in the results that were seen, but were unvisited due to scope or depth. Defaults to False.'
    )
    parser.add_argument(
        '--silent',
        action='store_true',  # The argument will be True if provided, False if not
        help='Flag to run without live curses output. Defaults to False.'
    )

    parser.add_argument(
        '--blacklist',
        type=str,
        required=False, 
        help='A file with a list of blacklist regex to avoid when crawling'
    )

    parser.add_argument(
        '--canary',
        choices=['basic', 'adaptive'],  # The allowed values for the argument
        help='Use a basic or adaptive HTTP WAF Canary'
    )
    parser.add_argument(
        '--proxy',
        type=str,
        required=False, 
        help='HTTP/S proxy to tunnel requests through',
        metavar='HOST:PORT'
    )
    
    parser.add_argument(
        '--render',
        action='store_true',  # The argument will be True if provided, False if not
        help='Flag to use Firefox/GeckoDriver to render dynamic webpages. Defaults to False. (Can be slow and resource intensive)'
    )
    parser.add_argument(
        '--no-headless',
        action='store_true',
        help='Wanna watch the Rendering Drivers work?'
    )
    parser.add_argument(
        '--drivers',
        type=int,
        default=1,  # Default value if the argument is not provided
        help='Number of Rendering Drivers to use if rendering (Default 1) (WARNING: This number is doubled whenever the render, auth, and subdomains args are used together)',
        metavar="NUM"
    )

    parser.add_argument(
        '--builders',
        type=int,
        default=1,  # Default value if the argument is not provided
        help='Number of Request Builders (Default 1)',
        metavar="NUM"
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=5,  # Default value if the argument is not provided
        help='Number of Request Workers (Default 5)',
        metavar="NUM"
    )
    parser.add_argument(
        '--parsers',
        type=int,
        default=2,  # Default value if the argument is not provided
        help='Number of Response Parsers (Default 2)',
        metavar="NUM"
    )
    parser.add_argument(
        '--db-workers',
        type=int,
        default=3,  # Default value if the argument is not provided
        help='Number of DB Workers (Default 3)',
        metavar="NUM"
    )
    
    args = parser.parse_args()

    oe = OmenEye(
        url=args.url,
        db_name=args.output,
        seed_file=args.seed_file,
        mitm_port=args.mitm,
        max_depth=args.depth,
        delay=args.delay,
        jitter=args.jitter,
        robots=args.robots,
        sitemaps=args.sitemaps,
        subdomains=args.subdomains,
        js_grabbing=args.js_grabbing,
        unvisited=args.unvisited,
        blacklist_file=args.blacklist,
        canary=args.canary,
        proxy=args.proxy,
        render=args.render,
        headless=(not args.no_headless),
        num_drivers=args.drivers,
        num_request_builders=args.builders,
        num_request_workers=args.workers,
        num_response_parsers=args.parsers,
        num_db_workers=args.db_workers,
    )

    if args.silent:
        oe.run()
    else:
        oe.run_live()

    