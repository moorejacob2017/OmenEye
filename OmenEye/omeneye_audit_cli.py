import sqlite3
import html
import re
import os
import mimetypes
import argparse
import zipfile
from urllib.parse import urlparse
from collections import defaultdict
from bs4 import BeautifulSoup

#==================================================

def generate_tree_from_structure(data_structure):
    """
    Generates a tree-like string representation of a given data structure.

    Args:
    - data_structure: The nested dictionary or list to represent as a tree.

    Returns:
    A string representing the tree structure.
    """

    def add_path_to_tree(tree, path_list, body):
        """
        Recursively adds paths to the tree structure.

        Args:
        - tree: The current level of the tree.
        - path_list: The list of path segments.
        - body: The content to store at the final path segment.
        """
        if len(path_list) == 1:
            tree[path_list[0]] = body
        else:
            if path_list[0] not in tree:
                tree[path_list[0]] = {}
            add_path_to_tree(tree[path_list[0]], path_list[1:], body)

    def build_tree_structure(data, prefix=""):
        """
        Recursively builds a tree structure from nested dictionaries and lists.
        
        Args:
        - data: The nested dictionary or list to represent.
        - prefix: The prefix string used for indentation.
        
        Returns:
        A string representing the tree structure.
        """
        tree = ""
        if isinstance(data, dict):
            entries = sorted(data.items())
            for i, (key, value) in enumerate(entries):
                connector = "└── " if i == len(entries) - 1 else "├── "
                tree += f"{prefix}{connector}{key}\n"
                tree += build_tree_structure(value, prefix + ("    " if i == len(entries) - 1 else "│   "))
        elif isinstance(data, list):
            for i, item in enumerate(data):
                connector = "└── " if i == len(data) - 1 else "├── "
                tree += f"{prefix}{connector}{item}\n"
                if isinstance(item, (dict, list)):
                    tree += build_tree_structure(item, prefix + ("    " if i == len(data) - 1 else "│   "))
        return tree

    nested_structure = {}
    for path, body in data_structure.items():
        path_parts = path.split(os.sep)
        add_path_to_tree(nested_structure, path_parts, body)
    
    tree_string = ".\n" + build_tree_structure(nested_structure)
    return tree_string

#====================================================================================================
# ACTIVE USAGE REQUIRED
def get_body_regex(cursor, regex_pattern):
    # Compile the regular expression
    regex = re.compile(regex_pattern.encode('utf-8'))
    
    # Prepare the query to fetch all response bodies
    query = "SELECT body FROM responses"
    
    # Execute the query
    cursor.execute(query)
    
    # Fetch all results
    results = cursor.fetchall()
    
    # List to store matching portions
    matching_portions = []
    
    # Iterate through the results and check for matches
    for (body,) in results:
        # Decode the body if it's stored as bytes
        #if isinstance(body, bytes):
        #    body = body.decode('utf-8', errors='ignore')
        
        # Find all matching portions in the body
        print(type(body))
        if body:
            matches = regex.findall(body)
        
            # Extend the list with all matches found in this body
            matching_portions.extend(matches)
    
    return matching_portions

def get_urls_matching_body_regex(cursor, regex_pattern):
    # Compile the regular expression
    regex = re.compile(regex_pattern.encode('utf-8'))
    
    # Prepare the query to fetch all response bodies and their associated URLs
    query = "SELECT url, body FROM responses"
    
    # Execute the query
    cursor.execute(query)
    
    # Fetch all results
    results = cursor.fetchall()
    
    # List to store matching URLs
    matching_urls = []
    
    # Iterate through the results and check for matches
    for url, body in results:
        # Decode the body if it's stored as bytes
        #if isinstance(body, bytes):
        #    body = body.decode('utf-8', errors='ignore')
        
        # Check if the body matches the regex pattern
        if body:
            if regex.search(body):
                matching_urls.append(url)
    
    return matching_urls

def get_html_bodies(cursor):
    # Prepare the query to fetch response bodies with Content-Type 'text/html'
    query = """
    SELECT r.body
    FROM responses r
    JOIN headers h ON r.response_id = h.response_id
    WHERE h.header_name = 'Content-Type' AND h.header_value LIKE 'text/html%'
    """
    
    # Execute the query
    cursor.execute(query)
    
    # Fetch all results
    results = cursor.fetchall()
    
    # List to store HTML bodies
    html_bodies = []
    
    # Iterate through the results and decode the body if necessary
    for (body,) in results:
        # Decode the body if it's stored as bytes
        if isinstance(body, bytes):
            body = body.decode('utf-8', errors='ignore')
        
        # Add the decoded body to the list
        html_bodies.append(body)
    
    return html_bodies

#====================================================================================================
# STATS & INFO

def general_stats(cursor):
    md = "## Stats\n"

    query = '''
    SELECT COUNT(DISTINCT url) AS unique_urls_count
    FROM responses;
    '''
    (url_count,) = cursor.execute(query).fetchone()
    md += f"- {url_count} URLs seen\n"

    query = '''
    SELECT COUNT(DISTINCT status_code) AS unique_status_code
    FROM responses
    '''
    (st_count,) = cursor.execute(query).fetchone()
    md += f"- {st_count} Unique Status Codes recieved\n"
    
    query = '''
    SELECT COUNT(DISTINCT link) AS unique_links_count
    FROM links;
    '''
    (link_count,) = cursor.execute(query).fetchone()
    md += f"- {link_count} Links found\n"

    query = '''
    SELECT COUNT(DISTINCT header_name) AS unique_header_count
    FROM headers;
    '''
    (header_count,) = cursor.execute(query).fetchone()
    md += f"- {header_count} Headers seen\n"

    query = '''
    SELECT COUNT(DISTINCT param_name) AS unique_qp_count
    FROM query_params;
    '''
    (qp_count,) = cursor.execute(query).fetchone()
    md += f"- {qp_count} Query Parameters seen\n"

    query = '''
    SELECT COUNT(DISTINCT tag) AS unique_input_count
    FROM inputs;
    '''
    (input_count,) = cursor.execute(query).fetchone()
    query = '''
    SELECT COUNT(DISTINCT r.url) AS unique_input_url_count
    FROM responses r
    JOIN inputs i ON r.response_id = i.response_id
    ORDER BY r.url
    '''
    (input_url_count,) = cursor.execute(query).fetchone()
    md += f"- {input_count} Input Tags found across {input_url_count} unique URLs\n"

    query = '''
    SELECT COUNT(DISTINCT header_value) AS unique_content_types
    FROM headers
    WHERE header_name = 'Content-Type';
    '''
    (ct_count,) = cursor.execute(query).fetchone()
    md += f"- {ct_count} Unique Content Types requested\n"

    return md

def status_code_stats_markdown(cursor):
    query = '''
    SELECT COUNT(*) as count, status_code 
    FROM responses
    WHERE status_code IS NOT NULL
    GROUP BY status_code
    ORDER BY count DESC;
    '''
    md = "## Status Codes\n"
    md += "| status code | number of instances |\n"
    md += "| -------- | -------- |\n"
    codes = cursor.execute(query)
    for count, status_code in codes:
        md += f"| {status_code} | {count} |\n"
    return md

def header_stats_markdown(cursor):
    query = '''
    SELECT header_name, 
           COUNT(*) AS count_instances, 
           COUNT(DISTINCT header_value) AS count_unique_values
    FROM headers
    GROUP BY header_name
    '''
    md = "## Headers\n"
    md += "| headers | number of instances | number of unique values |\n"
    md += "| -------- | ---------------- | ------------------- |\n"
    headers = cursor.execute(query)
    for header, count_instances, count_unique_values in headers:
        md += f"| {header} | {count_instances} | {count_unique_values} |\n"
    return md

def content_type_stats_markdown(cursor):
    query = '''
    SELECT COUNT(*) as count, header_value
    FROM headers
    WHERE header_name == 'Content-Type'
    GROUP BY header_value
    '''
    md = "## Content Types\n"
    md += "| content type | number of instances |\n"
    md += "| -------- | ---------------- |\n"
    content_types = cursor.execute(query)
    for count, content_type in content_types:
        _ct = html.escape(content_type)
        md += f"| {_ct} | {count} |\n"
    return md

def stats_md(cursor): 
    query = '''
    SELECT url
    FROM responses
    WHERE response_id == 1;
    '''
    (url,) = cursor.execute(query).fetchone()
    domain = urlparse(url).netloc

    md = f"# {domain}\n"
    md += "- [Stats](#stats)\n"
    md += "- [Status Codes](#status-codes)\n"
    md += "- [Headers](#headers)\n"
    md += "- [Content Types](#content-types)\n"

    md += general_stats(cursor)
    md += status_code_stats_markdown(cursor)
    md += header_stats_markdown(cursor)
    md += content_type_stats_markdown(cursor)
    return md



def qp_value_tree(cursor):
    
    query = '''
    SELECT param_name, param_value
    FROM query_params
    ORDER BY param_name, param_value;
    '''

    # Execute the query
    cursor.execute(query)
    
    # Fetch all results
    results = cursor.fetchall()
    
    # Dictionary to store all tag attributes and their values
    params = {}

    for (param, value) in results:
        if param not in params:
            params[param] = []
        params[param].append(value)

    keys = list(params.keys())
    for key in keys:
        params[key] = list(set(params[key]))
        if '' in params[key]:
            params[key].remove('')
        if ' ' in params[key]:
            params[key].remove(' ')
        params[key].sort()

    return generate_tree_from_structure(params)

def header_values_tree(cursor):
    
    query = '''
    SELECT header_name, header_value
    FROM headers
    ORDER BY header_name, header_value;
    '''

    # Execute the query
    cursor.execute(query)
    
    # Fetch all results
    results = cursor.fetchall()
    
    # Dictionary to store all tag attributes and their values
    headers = {}

    for (header, value) in results:
        if header not in headers:
            headers[header] = []
        headers[header].append(value)

    keys = list(headers.keys())
    for key in keys:
        headers[key] = list(set(headers[key]))
        if '' in headers[key]:
            headers[key].remove('')
        if ' ' in headers[key]:
            headers[key].remove(' ')
        headers[key].sort()

    return generate_tree_from_structure(headers)

def tag_attribute_tree(cursor):
    # Prepare the query to fetch response bodies with Content-Type 'text/html'
    query = """
    SELECT r.body
    FROM responses r
    JOIN headers h ON r.response_id = h.response_id
    WHERE h.header_name = 'Content-Type' AND h.header_value LIKE 'text/html%'
    """
    
    # Execute the query
    cursor.execute(query)
    
    # Fetch all results
    results = cursor.fetchall()
    
    # Dictionary to store all tag attributes and their values
    tag_attributes = {}
    
    # Iterate through the results
    for (body,) in results:
        # Decode the body if it's stored as bytes
        if isinstance(body, bytes):
            body = body.decode('utf-8', errors='ignore')
        
        # Parse the HTML body with BeautifulSoup
        soup = BeautifulSoup(body, 'html.parser')
        
        # Find all tags and extract their attributes
        for tag in soup.find_all(True):  # True means all tags
            for attr, value in tag.attrs.items():
                if attr not in tag_attributes:
                    tag_attributes[attr] = []
                if isinstance(value, list):
                    if not value == []:
                        tag_attributes[attr].append(value[0])
                else:
                    tag_attributes[attr].append(value)
    
    # Get uniq elements
    keys = list(tag_attributes.keys())
    for key in keys:
        tag_attributes[key] = list(set(tag_attributes[key]))
        if '' in tag_attributes[key]:
            tag_attributes[key].remove('')
        if ' ' in tag_attributes[key]:
            tag_attributes[key].remove(' ')
        tag_attributes[key].sort()
        

    return generate_tree_from_structure(tag_attributes)

def tag_url_markdown(cursor):
    # Prepare the query to fetch all distinct tags from the inputs table
    tags_query = "SELECT DISTINCT tag FROM inputs"
    
    # Execute the query to fetch distinct tags
    cursor.execute(tags_query)
    
    # Fetch all distinct tags
    tags = cursor.fetchall()
    
    # Dictionary to store tags and associated URLs
    tag_urls = {}
    
    # Iterate over each tag
    for tag in tags:
        tag = tag[0]  # Extract the tag from the tuple
        
        # Prepare the query to fetch URLs associated with the current tag
        urls_query = '''
        SELECT DISTINCT r.url
        FROM responses r
        JOIN inputs i ON r.response_id = i.response_id
        WHERE i.tag = ?
        ORDER BY r.url;        
        '''
        
        # Execute the query with the current tag as a parameter
        cursor.execute(urls_query, (tag,))
        
        # Fetch all URLs associated with the current tag
        urls = cursor.fetchall()
        
        # Extract URLs from the result tuples and store them in the dictionary
        tag_urls[tag] = [url[0] for url in urls]

     # Get uniq elements
    keys = list(tag_urls.keys())
    for key in keys:
        tag_urls[key] = list(set(tag_urls[key]))
        if '' in tag_urls[key]:
            tag_urls[key].remove('')
        if ' ' in tag_urls[key]:
            tag_urls[key].remove(' ')
        tag_urls[key].sort()
    

    markdown_list = ""
    tags = list(tag_urls.keys())
    for tag in tags:
        markdown_list += '- [ ] ' + html.escape(tag) + "\n"
        for url in tag_urls[tag]:
            markdown_list += f"\t- [{url}]({url})\n"
        #markdown_list += "\n\n"

    return markdown_list

#====================================================================================================

def get_all_urls(cursor):
    query = '''
    SELECT DISTINCT url
    FROM responses
    ORDER BY url
    '''
    results = cursor.execute(query)
    urls = [url for (url,) in results]
    return urls

def get_all_links(cursor):
    query = '''
    SELECT DISTINCT link
    FROM links
    ORDER BY link
    '''
    results = cursor.execute(query)
    links = [link for (link,) in results]
    return links

def get_extension(content_type):
    # Use the mimetypes library to guess the extension
    extension = mimetypes.guess_extension(content_type.split(';')[0])
    # Default to .txt if no extension is found
    return extension if extension else '.txt'


def generate_links_sitemap(cursor):
    urls = get_all_urls(cursor)
    urls.extend(get_all_links(cursor))
    lsm = generate_sitemap_from_urls(urls)
    return lsm

def dump_all_bodies(cursor, base_dir):
    # Prepare the query to fetch response bodies, URLs, and content types
    query = """
    SELECT r.url, r.body, h.header_value
    FROM responses r
    JOIN headers h ON r.response_id = h.response_id
    WHERE h.header_name = 'Content-Type' AND r.body IS NOT NULL AND r.body != ''
    """
    
    # Execute the query
    cursor.execute(query)
    
    # Fetch all results
    results = cursor.fetchall()
    
    # Iterate through the results
    for url, body, content_type in results:
        # Decode the body if it's stored as bytes
        if isinstance(body, bytes):
            body = body.decode('utf-8', errors='ignore')
        
        # Parse the URL to get the domain name and path
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        path = parsed_url.path
        
        # Determine the file extension from the content type
        expected_extension = get_extension(content_type)
        
        # Create the directory structure
        file_dir = os.path.join(base_dir, domain, os.path.dirname(path).lstrip('/'))
        os.makedirs(file_dir, exist_ok=True)
        
        # Determine the base filename and extension
        base_filename, current_extension = os.path.splitext(os.path.basename(path))
        if not base_filename:  # If the path ends with a slash, use 'index'
            base_filename = 'index'
            current_extension = expected_extension
        
        # Add the expected extension if the current extension is not the same
        if current_extension != expected_extension:
            file_path = os.path.join(file_dir, base_filename + expected_extension)
        else:
            file_path = os.path.join(file_dir, base_filename + current_extension)
        
        # Resolve filename collisions
        counter = 1
        original_file_path = file_path
        while os.path.exists(file_path):
            file_name, file_extension = os.path.splitext(original_file_path)
            file_path = f"{file_name}_{counter}{file_extension}"
            counter += 1
        
        # Write the body to the file
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(body)
    
    print(f"Dumped {len(results)} response bodies to {base_dir}")

def generate_sitemap(cursor):
    # Prepare the query to fetch response bodies, URLs, and content types
    query = """
    SELECT r.url, r.body, h.header_value
    FROM responses r
    JOIN headers h ON r.response_id = h.response_id
    WHERE h.header_name = 'Content-Type' AND r.body IS NOT NULL AND r.body != ''
    """
    
    # Execute the query
    cursor.execute(query)
    
    # Fetch all results
    results = cursor.fetchall()
    
    # Store paths in a nested dictionary
    file_structure = defaultdict(dict)
    
    # Iterate through the results
    for url, body, content_type in results:
        # Decode the body if it's stored as bytes
        if isinstance(body, bytes):
            body = body.decode('utf-8', errors='ignore')
        
        # Parse the URL to get the domain name and path
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        path = parsed_url.path
        
        # Determine the file extension from the content type
        expected_extension = get_extension(content_type)
        
        # Create the directory structure
        file_dir = os.path.join(domain, os.path.dirname(path).lstrip('/'))
        
        # Determine the base filename and extension
        base_filename, current_extension = os.path.splitext(os.path.basename(path))
        if not base_filename:  # If the path ends with a slash, use 'index'
            base_filename = 'index'
            current_extension = expected_extension
        
        # Add the expected extension if the current extension is not the same
        if current_extension != expected_extension:
            file_path = os.path.join(file_dir, base_filename + expected_extension)
        else:
            file_path = os.path.join(file_dir, base_filename + current_extension)
        
        # Resolve filename collisions
        counter = 1
        original_file_path = file_path
        while file_path in file_structure[domain]:
            file_name, file_extension = os.path.splitext(original_file_path)
            file_path = f"{file_name}_{counter}{file_extension}"
            counter += 1
        
        # Store the file path
        file_structure[domain][file_path] = body
    
    # Convert the nested dictionary to a tree string format
    def build_tree(directory, prefix=""):
        tree = ""
        entries = sorted(directory.items())
        for i, (name, subtree) in enumerate(entries):
            connector = "└── " if i == len(entries) - 1 else "├── "
            if isinstance(subtree, dict):
                tree += f"{prefix}{connector}{name}/\n"
                tree += build_tree(subtree, prefix + ("    " if i == len(entries) - 1 else "│   "))
            else:
                tree += f"{prefix}{connector}{name}\n"
        return tree

    # Build the nested directory structure
    def add_path_to_tree(tree, path_list, body):
        if len(path_list) == 1:
            tree[path_list[0]] = body
        else:
            if path_list[0] not in tree:
                tree[path_list[0]] = {}
            add_path_to_tree(tree[path_list[0]], path_list[1:], body)

    nested_structure = {}
    for domain, files in file_structure.items():
        domain_parts = domain.split(os.sep)
        for file_path, body in files.items():
            path_parts = file_path.split(os.sep)
            add_path_to_tree(nested_structure, domain_parts + path_parts, body)
    
    sitemap = ".\n" + build_tree(nested_structure)

    #print(sitemap)

    # Optionally, write the sitemap to a file
    #with open(os.path.join("sitemap.txt"), "w", encoding="utf-8") as sitemap_file:
    #    sitemap_file.write(sitemap)

    #print(f"Generated sitemap for {len(results)} response bodies")
    return sitemap

def generate_sitemap_from_urls(urls):
    # Store paths in a nested dictionary
    file_structure = defaultdict(dict)
    
    # Iterate through the list of URLs
    for url in urls:
        # Parse the URL to get the domain name and path
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        path = parsed_url.path
        
        # Create the directory structure
        file_dir = os.path.join(domain, os.path.dirname(path).lstrip('/'))
        
        # Determine the base filename and extension
        base_filename, current_extension = os.path.splitext(os.path.basename(path))
        if not base_filename:  # If the path ends with a slash, use 'index'
            base_filename = 'index'
        
        file_path = os.path.join(file_dir, base_filename + current_extension)
        
        # Resolve filename collisions
        counter = 1
        original_file_path = file_path
        while file_path in file_structure[domain]:
            file_name, file_extension = os.path.splitext(original_file_path)
            file_path = f"{file_name}_{counter}{file_extension}"
            counter += 1
        
        # Store the file path
        file_structure[domain][file_path] = None  # No body to store, just the path
    
    # Convert the nested dictionary to a tree string format
    def build_tree(directory, prefix=""):
        tree = ""
        entries = sorted(directory.items())
        for i, (name, subtree) in enumerate(entries):
            connector = "└── " if i == len(entries) - 1 else "├── "
            if isinstance(subtree, dict):
                tree += f"{prefix}{connector}{name}/\n"
                tree += build_tree(subtree, prefix + ("    " if i == len(entries) - 1 else "│   "))
            else:
                tree += f"{prefix}{connector}{name}\n"
        return tree

    # Build the nested directory structure
    def add_path_to_tree(tree, path_list):
        if len(path_list) == 1:
            tree[path_list[0]] = {}
        else:
            if path_list[0] not in tree or tree[path_list[0]] is None:
                tree[path_list[0]] = {}
            add_path_to_tree(tree[path_list[0]], path_list[1:])

    nested_structure = {}
    for domain, files in file_structure.items():
        domain_parts = domain.split(os.sep)
        for file_path in files.keys():
            path_parts = file_path.split(os.sep)
            add_path_to_tree(nested_structure, domain_parts + path_parts)
    
    sitemap = ".\n" + build_tree(nested_structure)

    # Optionally, write the sitemap to a file
    #with open("sitemap.txt", "w", encoding="utf-8") as sitemap_file:
    #    sitemap_file.write(sitemap)

    #print(f"Generated sitemap for {len(urls)} URLs")

    return sitemap

#====================================================================================================

'''
def zip_and_remove(files, zip_name):
    if not zip_name.endswith('.zip'):
        zip_name += '.zip'
    
    with zipfile.ZipFile(zip_name, 'w') as zipf:
        for file in files:
            zipf.write(file, os.path.basename(file))
            os.remove(file)
'''


def zip_and_remove(files, zip_name):
    if not zip_name.endswith('.zip'):
        zip_name += '.zip'
    
    base_dir = os.path.splitext(zip_name)[0]
    
    with zipfile.ZipFile(zip_name, 'w') as zipf:
        for file in files:
            zipf.write(file, os.path.join(base_dir, os.path.basename(file)))
            os.remove(file)

    return zip_name


def generate_reports(cursor, file_name):
    all_urls = get_all_urls(cursor)
    with open('/tmp/urls.txt', 'w') as f:
        for url in all_urls:
            f.write(f"{url}\n")

    all_links = get_all_links(cursor)
    with open('/tmp/links.txt', 'w') as f:
        for link in all_links:
            f.write(f"{link}\n")

    sitemap = generate_sitemap(cursor)
    with open('/tmp/sitemap.tree', 'w') as f:
        f.write(sitemap)
    
    link_sitemap = generate_links_sitemap(cursor)
    with open('/tmp/link_sitemap.tree', 'w') as f:
        f.write(link_sitemap)

    hvt = header_values_tree(cursor)
    with open('/tmp/header_value.tree', 'w') as f:
        f.write(hvt)

    qpt = qp_value_tree(cursor)
    with open('/tmp/query_parameter_value.tree', 'w') as f:
        f.write(qpt)

    tat = tag_attribute_tree(cursor)
    with open('/tmp/tag_attribute_value.tree', 'w') as f:
        f.write(tat)

    itul = tag_url_markdown(cursor)
    with open('/tmp/input_tag_url_list.md', 'w') as f:
        f.write(itul)
    
    stats = stats_md(cursor)
    with open('/tmp/stats.md', 'w') as f:
        f.write(stats)

    files = [
        '/tmp/urls.txt',
        '/tmp/links.txt',
        '/tmp/sitemap.tree',
        '/tmp/link_sitemap.tree',
        '/tmp/header_value.tree',
        '/tmp/query_parameter_value.tree',
        '/tmp/tag_attribute_value.tree',
        '/tmp/input_tag_url_list.md',
        '/tmp/stats.md',
    ]

    zip_name = zip_and_remove(files, file_name)
    print(f"Generated analysis package located at {zip_name}")

    
    
    


























schema_text = '''

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
'''



def cli():
    parser = argparse.ArgumentParser(
        description="Analysis script for an Omen Eye database",
        epilog=schema_text,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-i", help="Name of the Omen Eye database", required=True, metavar="DATABASE")

    parser.add_argument("-a", help="Generate analysis files (zipped)", type=str, metavar="FILENAME")
    parser.add_argument("-d", help="Dump the response bodies to file", type=str, metavar="DIR")
    parser.add_argument("-r", help="Get content from bodies that matches regex", type=str, metavar="REGEX")
    parser.add_argument("-u", help="Get the urls that have bodies matching regex", type=str, metavar="REGEX")

    args = parser.parse_args()

    with sqlite3.connect(args.i) as conn:
        cursor = conn.cursor()

        if args.a:
            generate_reports(cursor, args.a)
        elif args.d:
            dump_all_bodies(cursor, args.d)
        elif args.r:
            matches = get_body_regex(cursor, args.r)
            for match in matches:
                print(match.decode('utf-8', errors='ignore'))
        elif args.u:
            matches = get_urls_matching_body_regex(cursor, args.u)
            for match in matches:
                print(match)

