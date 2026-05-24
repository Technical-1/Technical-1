import datetime
from dateutil import relativedelta
import requests
import os
from lxml import etree
import time
import hashlib

# Fine-grained personal access token with All Repositories access:
# Account permissions: read:Followers, read:Starring, read:Watching
# Repository permissions: read:Commit statuses, read:Contents, read:Issues, read:Metadata, read:Pull Requests
# Issues and pull requests permissions not needed at the moment, but may be used in the future
HEADERS = {'authorization': 'token '+ os.environ['ACCESS_TOKEN']}
USER_NAME = os.environ['USER_NAME'] # 'Andrew6rant'
QUERY_COUNT = {'user_getter': 0, 'follower_getter': 0, 'graph_repos_stars': 0, 'recursive_loc': 0, 'graph_commits': 0, 'loc_query': 0}


def daily_readme(birthday):
    """
    Returns the length of time since I was born
    e.g. 'XX years, XX months, XX days'
    """
    diff = relativedelta.relativedelta(datetime.datetime.today(), birthday)
    return '{} {}, {} {}, {} {}{}'.format(
        diff.years, 'year' + format_plural(diff.years), 
        diff.months, 'month' + format_plural(diff.months), 
        diff.days, 'day' + format_plural(diff.days),
        ' 🎂' if (diff.months == 0 and diff.days == 0) else '')


def format_plural(unit):
    """
    Returns a properly formatted number
    e.g.
    'day' + format_plural(diff.days) == 5
    >>> '5 days'
    'day' + format_plural(diff.days) == 1
    >>> '1 day'
    """
    return 's' if unit != 1 else ''


def abbreviate_number(num, suffix=''):
    """
    Abbreviates large numbers to K/M format for OG image display
    e.g. 20397754 -> '20.4M', 581234 -> '581.2K', 62 -> '62'
    """
    if num >= 1_000_000:
        return f'{num / 1_000_000:.1f}M{suffix}'
    elif num >= 1_000:
        return f'{num / 1_000:.1f}K{suffix}'
    return f'{num:,}{suffix}'


def simple_request(func_name, query, variables):
    """
    Returns a request, or raises an Exception if the response does not succeed.
    """
    request = requests.post('https://api.github.com/graphql', json={'query': query, 'variables':variables}, headers=HEADERS)
    if request.status_code == 200:
        return request
    raise Exception(func_name, ' has failed with a', request.status_code, request.text, QUERY_COUNT)


def graph_commits(start_date, end_date):
    """
    Uses GitHub's GraphQL v4 API to return my total commit count
    """
    query_count('graph_commits')
    query = '''
    query($start_date: DateTime!, $end_date: DateTime!, $login: String!) {
        user(login: $login) {
            contributionsCollection(from: $start_date, to: $end_date) {
                contributionCalendar {
                    totalContributions
                }
            }
        }
    }'''
    variables = {'start_date': start_date,'end_date': end_date, 'login': USER_NAME}
    request = simple_request(graph_commits.__name__, query, variables)
    return int(request.json()['data']['user']['contributionsCollection']['contributionCalendar']['totalContributions'])


def filter_owned_forks(edges):
    """
    Drop forks whose upstream parent is also in the edges list — counting both
    would double-count the same commits (e.g. an owned fork of a repo the user
    is also a COLLABORATOR on). Forks whose parent is NOT in the list still
    count, since their commits are the only place the user's work appears.
    """
    all_names = {e['node']['nameWithOwner'] for e in edges}
    return [
        e for e in edges
        if not (e['node'].get('isFork') and e['node'].get('parent') and e['node']['parent']['nameWithOwner'] in all_names)
    ]


def graph_repos_stars(count_type, owner_affiliation, cursor=None, edges_acc=None):
    """
    Uses GitHub's GraphQL v4 API to count repositories or sum stars, excluding
    owned forks whose upstream parent is also in the user's list.
    """
    if edges_acc is None:
        edges_acc = []
    query_count('graph_repos_stars')
    query = '''
    query ($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
        user(login: $login) {
            repositories(first: 100, after: $cursor, ownerAffiliations: $owner_affiliation) {
                edges {
                    node {
                        ... on Repository {
                            nameWithOwner
                            isFork
                            parent {
                                nameWithOwner
                            }
                            stargazers {
                                totalCount
                            }
                        }
                    }
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
    }'''
    variables = {'owner_affiliation': owner_affiliation, 'login': USER_NAME, 'cursor': cursor}
    request = simple_request(graph_repos_stars.__name__, query, variables)
    page = request.json()['data']['user']['repositories']
    edges_acc += page['edges']
    if page['pageInfo']['hasNextPage']:
        return graph_repos_stars(count_type, owner_affiliation, page['pageInfo']['endCursor'], edges_acc)
    filtered = filter_owned_forks(edges_acc)
    if count_type == 'repos':
        return len(filtered)
    elif count_type == 'stars':
        return stars_counter(filtered)


def recursive_loc(owner, repo_name, data, cache_comment, addition_total=0, deletion_total=0, my_commits=0, cursor=None, retry_count=0):
    """
    Uses GitHub's GraphQL v4 API and cursor pagination to fetch 50 commits from a repository at a time
    Includes retry logic for 502/503/504 gateway errors with exponential backoff
    """
    query_count('recursive_loc')
    query = '''
    query ($repo_name: String!, $owner: String!, $cursor: String) {
        repository(name: $repo_name, owner: $owner) {
            defaultBranchRef {
                target {
                    ... on Commit {
                        history(first: 50, after: $cursor) {
                            totalCount
                            edges {
                                node {
                                    ... on Commit {
                                        committedDate
                                    }
                                    author {
                                        user {
                                            id
                                        }
                                    }
                                    deletions
                                    additions
                                }
                            }
                            pageInfo {
                                endCursor
                                hasNextPage
                            }
                        }
                    }
                }
            }
        }
    }'''
    variables = {'repo_name': repo_name, 'owner': owner, 'cursor': cursor}
    # Small delay to avoid rate limiting and gateway errors
    if cursor is not None:
        time.sleep(0.75)  # 750ms delay between paginated requests
    try:
        request = requests.post('https://api.github.com/graphql', json={'query': query, 'variables':variables}, headers=HEADERS, timeout=30) # I cannot use simple_request(), because I want to save the file before raising Exception
    except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError, requests.exceptions.Timeout) as e:
        if retry_count < 5:
            wait_time = (2 ** retry_count) * 3  # Exponential backoff: 3s, 6s, 12s, 24s, 48s
            print(f'Network error for {owner}/{repo_name}, retrying in {wait_time}s (attempt {retry_count + 1}/5)...')
            time.sleep(wait_time)
            return recursive_loc(owner, repo_name, data, cache_comment, addition_total, deletion_total, my_commits, cursor, retry_count + 1)
        force_close_file(data, cache_comment)
        raise Exception(f'recursive_loc() network error after 5 retries: {e}')
    # Parse JSON defensively: GitHub sometimes returns HTTP 200 with a truncated/empty
    # body when its backend is degraded (same root cause as 502/503/504 on this repo).
    # Treat both modes as a single "degraded response" signal.
    try:
        response_body = request.json()
    except requests.exceptions.JSONDecodeError:
        response_body = None

    if response_body is not None and request.status_code == 200:
        branch_ref = response_body['data']['repository']['defaultBranchRef']
        if branch_ref is not None:
            return loc_counter_one_repo(owner, repo_name, data, cache_comment, branch_ref['target']['history'], addition_total, deletion_total, my_commits)
        return 0
    force_close_file(data, cache_comment) # saves what is currently in the file before this program crashes
    if request.status_code == 403:
        raise Exception('Too many requests in a short amount of time!\nYou\'ve hit the non-documented anti-abuse limit!')
    # Degraded backend: gateway error OR 200-with-malformed-body. Retry with backoff,
    # then cache as SKIP so future runs don't re-query until commit_count changes.
    degraded = response_body is None or request.status_code in [502, 503, 504]
    if degraded and retry_count < 5:
        wait_time = (2 ** retry_count) * 3  # Exponential backoff: 3s, 6s, 12s, 24s, 48s
        reason = f'{request.status_code} error' if response_body is not None else 'empty/malformed JSON response'
        print(f'{reason} for {owner}/{repo_name}, retrying in {wait_time}s (attempt {retry_count + 1}/5)...')
        time.sleep(wait_time)
        return recursive_loc(owner, repo_name, data, cache_comment, addition_total, deletion_total, my_commits, cursor, retry_count + 1)
    if degraded:
        print(f'WARNING: {owner}/{repo_name} degraded after 5 retries (last status {request.status_code}) — caching as skipped (will retry when commit count changes).')
        return 'SKIP'
    raise Exception('recursive_loc() has failed with a', request.status_code, request.text, QUERY_COUNT)


def loc_counter_one_repo(owner, repo_name, data, cache_comment, history, addition_total, deletion_total, my_commits):
    """
    Recursively call recursive_loc (since GraphQL can only search 100 commits at a time) 
    only adds the LOC value of commits authored by me
    """
    for node in history['edges']:
        if node['node']['author']['user'] == OWNER_ID:
            my_commits += 1
            addition_total += node['node']['additions']
            deletion_total += node['node']['deletions']

    if history['edges'] == [] or not history['pageInfo']['hasNextPage']:
        return addition_total, deletion_total, my_commits
    else: return recursive_loc(owner, repo_name, data, cache_comment, addition_total, deletion_total, my_commits, history['pageInfo']['endCursor'])


def loc_query(owner_affiliation, comment_size=0, force_cache=False, cursor=None, edges=[]):
    """
    Uses GitHub's GraphQL v4 API to query all the repositories I have access to (with respect to owner_affiliation)
    Queries 60 repos at a time, because larger queries give a 502 timeout error and smaller queries send too many
    requests and also give a 502 error.
    Returns the total number of lines of code in all repositories
    """
    query_count('loc_query')
    query = '''
    query ($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
        user(login: $login) {
            repositories(first: 60, after: $cursor, ownerAffiliations: $owner_affiliation) {
            edges {
                node {
                    ... on Repository {
                        nameWithOwner
                        isFork
                        parent {
                            nameWithOwner
                        }
                        defaultBranchRef {
                            target {
                                ... on Commit {
                                    history {
                                        totalCount
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                pageInfo {
                    endCursor
                    hasNextPage
                }
            }
        }
    }'''
    variables = {'owner_affiliation': owner_affiliation, 'login': USER_NAME, 'cursor': cursor}
    request = simple_request(loc_query.__name__, query, variables)
    if request.json()['data']['user']['repositories']['pageInfo']['hasNextPage']:   # If repository data has another page
        edges += request.json()['data']['user']['repositories']['edges']            # Add on to the LoC count
        return loc_query(owner_affiliation, comment_size, force_cache, request.json()['data']['user']['repositories']['pageInfo']['endCursor'], edges)
    else:
        all_edges = edges + request.json()['data']['user']['repositories']['edges']
        return cache_builder(filter_owned_forks(all_edges), comment_size, force_cache)


def cache_builder(edges, comment_size, force_cache, loc_add=0, loc_del=0):
    """
    Checks each repository in edges to see if it has been updated since the last time it was cached
    If it has, run recursive_loc on that repository to update the LOC count
    """
    cached = True # Assume all repositories are cached
    filename = 'cache/'+hashlib.sha256(USER_NAME.encode('utf-8')).hexdigest()+'.txt' # Create a unique filename for each user
    try:
        with open(filename, 'r') as f:
            data = f.readlines()
    except FileNotFoundError: # If the cache file doesn't exist, create it
        data = []
        if comment_size > 0:
            for _ in range(comment_size): data.append('This line is a comment block. Write whatever you want here.\n')
        with open(filename, 'w') as f:
            f.writelines(data)

    if len(data)-comment_size != len(edges) or force_cache: # If the number of repos has changed, or force_cache is True
        cached = False
        flush_cache(edges, filename, comment_size)
        with open(filename, 'r') as f:
            data = f.readlines()

    cache_comment = data[:comment_size] # save the comment block
    data = data[comment_size:] # remove those lines
    for index in range(len(edges)):
        parts = data[index].split()
        repo_hash, commit_count = parts[0], parts[1]
        # Preserve prior LOC values for the SKIP fallback. flush_cache writes
        # 5-field rows so these are safe to read; fall back to '0' just in case.
        prev_my_commits = parts[2] if len(parts) > 2 else '0'
        prev_add = parts[3] if len(parts) > 3 else '0'
        prev_del = parts[4] if len(parts) > 4 else '0'
        if repo_hash == hashlib.sha256(edges[index]['node']['nameWithOwner'].encode('utf-8')).hexdigest():
            try:
                live_total = edges[index]['node']['defaultBranchRef']['target']['history']['totalCount']
                if int(commit_count) != live_total:
                    # if commit count has changed, update loc for that repo
                    owner, repo_name = edges[index]['node']['nameWithOwner'].split('/')
                    loc = recursive_loc(owner, repo_name, data, cache_comment)
                    if loc == 'SKIP':
                        # Keep yesterday's LOC values; only update commit_count to
                        # live_total. Zeroing here would corrupt the displayed total
                        # when a known-good repo hits a temporary GitHub backend issue
                        # (this caused a 20M → 4M regression on 2026-05-24).
                        data[index] = ' '.join([repo_hash, str(live_total), prev_my_commits, prev_add, prev_del]) + '\n'
                    else:
                        data[index] = repo_hash + ' ' + str(live_total) + ' ' + str(loc[2]) + ' ' + str(loc[0]) + ' ' + str(loc[1]) + '\n'
            except TypeError: # If the repo is empty
                data[index] = repo_hash + ' 0 0 0 0\n'
    with open(filename, 'w') as f:
        f.writelines(cache_comment)
        f.writelines(data)
    for line in data:
        loc = line.split()
        loc_add += int(loc[3])
        loc_del += int(loc[4])
    return [loc_add, loc_del, loc_add - loc_del, cached]


def flush_cache(edges, filename, comment_size):
    """
    Rebuild the cache to match the current edges list. Preserves prior LOC values
    for repos that survive (matched by hash) so a changed repo set (added/removed
    repo, or a fork filter that shrinks the list) doesn't wipe LOC data we already
    paid to compute.
    """
    with open(filename, 'r') as f:
        existing = f.readlines()
    comment = existing[:comment_size] if comment_size > 0 else []
    prior_by_hash = {}
    for line in existing[comment_size:]:
        parts = line.split()
        if parts:
            prior_by_hash[parts[0]] = line
    with open(filename, 'w') as f:
        f.writelines(comment)
        for node in edges:
            repo_hash = hashlib.sha256(node['node']['nameWithOwner'].encode('utf-8')).hexdigest()
            f.write(prior_by_hash.get(repo_hash, repo_hash + ' 0 0 0 0\n'))


def add_archive():
    """
    Several repositories I have contributed to have since been deleted.
    This function adds them using their last known data
    """
    with open('cache/repository_archive.txt', 'r') as f:
        data = f.readlines()
    old_data = data
    data = data[7:len(data)-3] # remove the comment block    
    added_loc, deleted_loc, added_commits = 0, 0, 0
    contributed_repos = len(data)
    for line in data:
        repo_hash, total_commits, my_commits, *loc = line.split()
        added_loc += int(loc[0])
        deleted_loc += int(loc[1])
        if (my_commits.isdigit()): added_commits += int(my_commits)
    added_commits += int(old_data[-1].split()[4][:-1])
    return [added_loc, deleted_loc, added_loc - deleted_loc, added_commits, contributed_repos]

def force_close_file(data, cache_comment):
    """
    Forces the file to close, preserving whatever data was written to it
    This is needed because if this function is called, the program would've crashed before the file is properly saved and closed
    """
    filename = 'cache/'+hashlib.sha256(USER_NAME.encode('utf-8')).hexdigest()+'.txt'
    with open(filename, 'w') as f:
        f.writelines(cache_comment)
        f.writelines(data)
    print('There was an error while writing to the cache file. The file,', filename, 'has had the partial data saved and closed.')


def stars_counter(data):
    """
    Count total stars in repositories owned by me
    """
    total_stars = 0
    for node in data: total_stars += node['node']['stargazers']['totalCount']
    return total_stars


def svg_overwrite(filename, commit_data, star_data, repo_data, contrib_data, follower_data, loc_data):
    """
    Parse SVG files and update elements with commits, stars, repositories, and lines written
    """
    tree = etree.parse(filename)
    root = tree.getroot()
    justify_format(root, 'commit_data', commit_data, 22)
    justify_format(root, 'star_data', star_data, 14)
    justify_format(root, 'repo_data', repo_data, 6)
    justify_format(root, 'contrib_data', contrib_data)
    justify_format(root, 'follower_data', follower_data, 10)
    justify_format(root, 'loc_data', loc_data[2], 9)
    justify_format(root, 'loc_add', loc_data[0])
    justify_format(root, 'loc_del', loc_data[1], 7)
    tree.write(filename, encoding='utf-8', xml_declaration=True)


def justify_format(root, element_id, new_text, length=0):
    """
    Updates and formats the text of the element, and modifes the amount of dots in the previous element to justify the new text on the svg
    """
    if isinstance(new_text, int):
        new_text = f"{'{:,}'.format(new_text)}"
    new_text = str(new_text)
    find_and_replace(root, element_id, new_text)
    just_len = max(0, length - len(new_text))
    if just_len <= 2:
        dot_map = {0: '', 1: ' ', 2: '. '}
        dot_string = dot_map[just_len]
    else:
        dot_string = ' ' + ('.' * just_len) + ' '
    find_and_replace(root, f"{element_id}_dots", dot_string)


def find_and_replace(root, element_id, new_text):
    """
    Finds the element in the SVG file and replaces its text with a new value
    """
    element = root.find(f".//*[@id='{element_id}']")
    if element is not None:
        element.text = None  # Clear existing text first
        element.text = new_text


def html_overwrite(filename, repo_data, commit_data, star_data, loc_data):
    """
    Updates og-preview.html with current GitHub stats using regex replacement.
    Mirrors the pattern of svg_overwrite() but targets HTML elements by id attribute.
    loc_data is [additions_str, deletions_str, net_str] with comma-formatted strings.
    """
    import re
    with open(filename, 'r', encoding='utf-8') as f:
        html = f.read()

    additions = int(loc_data[0].replace(',', ''))
    deletions = int(loc_data[1].replace(',', ''))
    net_loc = int(loc_data[2].replace(',', ''))

    stats = {
        'stat-repos': f'{repo_data:,}',
        'stat-commits': abbreviate_number(commit_data),
        'stat-stars': f'{star_data:,}',
        'stat-loc-net': abbreviate_number(net_loc),
        'stat-loc-add': abbreviate_number(additions, '++'),
        'stat-loc-del': abbreviate_number(deletions, '--'),
    }

    for stat_id, value in stats.items():
        html = re.sub(
            f'(<[^>]*id="{stat_id}"[^>]*>)[^<]*(</)',
            rf'\g<1>{value}\2',
            html
        )

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)


def render_og_image(html_path, output_path):
    """
    Renders og-preview.html to a 2x retina PNG using Playwright.
    Waits for Google Fonts to load before capturing.
    """
    from playwright.sync_api import sync_playwright

    abs_path = os.path.abspath(html_path)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={'width': 1200, 'height': 630},
            device_scale_factor=2
        )
        page.goto(f'file://{abs_path}')
        page.wait_for_load_state('networkidle')
        page.evaluate_handle('document.fonts.ready')
        page.wait_for_timeout(500)

        card = page.query_selector('.og-card')
        card.screenshot(path=output_path)
        browser.close()


def commit_counter(comment_size):
    """
    Counts up my total commits, using the cache file created by cache_builder.
    """
    total_commits = 0
    filename = 'cache/'+hashlib.sha256(USER_NAME.encode('utf-8')).hexdigest()+'.txt' # Use the same filename as cache_builder
    with open(filename, 'r') as f:
        data = f.readlines()
    cache_comment = data[:comment_size] # save the comment block
    data = data[comment_size:] # remove those lines
    for line in data:
        total_commits += int(line.split()[2])
    return total_commits


def user_getter(username):
    """
    Returns the account ID and creation time of the user
    """
    query_count('user_getter')
    query = '''
    query($login: String!){
        user(login: $login) {
            id
            createdAt
        }
    }'''
    variables = {'login': username}
    request = simple_request(user_getter.__name__, query, variables)
    return {'id': request.json()['data']['user']['id']}, request.json()['data']['user']['createdAt']

def follower_getter(username):
    """
    Returns the number of followers of the user
    """
    query_count('follower_getter')
    query = '''
    query($login: String!){
        user(login: $login) {
            followers {
                totalCount
            }
        }
    }'''
    request = simple_request(follower_getter.__name__, query, {'login': username})
    return int(request.json()['data']['user']['followers']['totalCount'])


def query_count(funct_id):
    """
    Counts how many times the GitHub GraphQL API is called
    """
    global QUERY_COUNT
    QUERY_COUNT[funct_id] += 1


def perf_counter(funct, *args):
    """
    Calculates the time it takes for a function to run
    Returns the function result and the time differential
    """
    start = time.perf_counter()
    funct_return = funct(*args)
    return funct_return, time.perf_counter() - start


def formatter(query_type, difference, funct_return=False, whitespace=0):
    """
    Prints a formatted time differential
    Returns formatted result if whitespace is specified, otherwise returns raw result
    """
    print('{:<23}'.format('   ' + query_type + ':'), sep='', end='')
    print('{:>12}'.format('%.4f' % difference + ' s ')) if difference > 1 else print('{:>12}'.format('%.4f' % (difference * 1000) + ' ms'))
    if whitespace:
        return f"{'{:,}'.format(funct_return): <{whitespace}}"
    return funct_return


if __name__ == '__main__':
    """
    Original work by Andrew Grant (Andrew6rant), 2022-2025
    Adapted by Jacob Kanfer (Technical-1), 2025
    """
    print('Calculation times:')
    # define global variable for owner ID and calculate user's creation date
    # e.g {'id': 'MDQ6VXNlcjU3MzMxMTM0'} and 2019-11-03T21:15:07Z for username 'Andrew6rant'
    user_data, user_time = perf_counter(user_getter, USER_NAME)
    OWNER_ID, acc_date = user_data
    formatter('account data', user_time)
    total_loc, loc_time = perf_counter(loc_query, ['OWNER', 'COLLABORATOR', 'ORGANIZATION_MEMBER'], 7)
    formatter('LOC (cached)', loc_time) if total_loc[-1] else formatter('LOC (no cache)', loc_time)
    commit_data, commit_time = perf_counter(commit_counter, 7)
    star_data, star_time = perf_counter(graph_repos_stars, 'stars', ['OWNER'])
    repo_data, repo_time = perf_counter(graph_repos_stars, 'repos', ['OWNER'])
    contrib_data, contrib_time = perf_counter(graph_repos_stars, 'repos', ['OWNER', 'COLLABORATOR', 'ORGANIZATION_MEMBER'])
    follower_data, follower_time = perf_counter(follower_getter, USER_NAME)

    # Archived repositories can be added here if needed
    # Uncomment and update OWNER_ID check if you have deleted repositories to include
    # if OWNER_ID == {'id': 'YOUR_USER_ID_HERE'}:
    #     archived_data = add_archive()
    #     for index in range(len(total_loc)-1):
    #         total_loc[index] += archived_data[index]
    #     contrib_data += archived_data[-1]
    #     commit_data += int(archived_data[-2])

    for index in range(len(total_loc)-1): total_loc[index] = '{:,}'.format(total_loc[index]) # format added, deleted, and total LOC

    svg_overwrite('full/dark_mode.svg', commit_data, star_data, repo_data, contrib_data, follower_data, total_loc[:-1])
    svg_overwrite('full/light_mode.svg', commit_data, star_data, repo_data, contrib_data, follower_data, total_loc[:-1])
    svg_overwrite('compact/dark_mode_simple.svg', commit_data, star_data, repo_data, contrib_data, follower_data, total_loc[:-1])
    svg_overwrite('compact/light_mode_simple.svg', commit_data, star_data, repo_data, contrib_data, follower_data, total_loc[:-1])

    # Update and render OG preview image
    html_overwrite('og-preview.html', repo_data, commit_data, star_data, total_loc[:-1])
    render_og_image('og-preview.html', '.portfolio/preview.png')

    # move cursor to override 'Calculation times:' with 'Total function time:' and the total function time, then move cursor back
    print('\033[F\033[F\033[F\033[F\033[F\033[F\033[F',
        '{:<21}'.format('Total function time:'), '{:>11}'.format('%.4f' % (user_time + loc_time + commit_time + star_time + repo_time + contrib_time)),
        ' s \033[E\033[E\033[E\033[E\033[E\033[E\033[E', sep='')

    print('Total GitHub GraphQL API calls:', '{:>3}'.format(sum(QUERY_COUNT.values())))
    for funct_name, count in QUERY_COUNT.items(): print('{:<28}'.format('   ' + funct_name + ':'), '{:>6}'.format(count))