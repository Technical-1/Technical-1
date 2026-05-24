# Languages-by-LOC SVG widget — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 850×255 SVG below the existing stats widget showing the user's top programming languages by user-authored lines of code, in dark and light modes that match the existing `compact/*_simple.svg` aesthetic exactly.

**Architecture:** Extend `loc_query`'s existing GraphQL with one new field (`primaryLanguage { name color }`). After `cache_builder` finishes per-repo LOC, aggregate `additions` by primary language into top-6 + Other, write to a sidecar cache file (`cache/<user-hash>_langs.txt`), then render dark/light SVGs with Unicode-block bars from the sidecar. New SVG files generated alongside the existing pair every workflow run; README updated with a second `<picture>` block.

**Tech Stack:** Python 3.12, `requests` (existing), `hashlib` (existing). No new dependencies. No test framework — verification is inline `python3 -c` assertions for pure functions and visual inspection for SVG output.

**Spec:** `docs/superpowers/specs/2026-05-24-languages-by-loc-svg-design.md`

---

## File Structure

**Modify:**
- `scripts/today.py` (only file edited):
  - `loc_query` (line ~228): add `primaryLanguage { name color }` to GraphQL query
  - `cache_builder` (line ~278): call new `aggregate_and_cache_languages()` helper just before returning
  - New helpers added below `flush_cache` (around line 340): `aggregate_languages`, `bar_blocks_for`, `write_language_cache`, `read_language_cache`, `render_languages_svg`
  - `__main__` block (line ~625): two new `render_languages_svg()` calls after the four existing `svg_overwrite()` calls
- `README.md` (line 1-6): add second `<picture>` block under the existing one

**Created by the script at runtime (no manual creation):**
- `compact/dark_mode_languages.svg`
- `compact/light_mode_languages.svg`
- `cache/<user-hash>_langs.txt`

---

## Task 1: Add `primaryLanguage` to GraphQL query

**Files:**
- Modify: `scripts/today.py:228-254` (the `query` string inside `loc_query`)

- [ ] **Step 1: Write the failing verification**

Save this scratch script as `/tmp/verify_lang_field.py`:

```python
import re
with open('scripts/today.py') as f:
    src = f.read()
# Find the loc_query function body
m = re.search(r'def loc_query.*?(?=\ndef )', src, re.DOTALL)
assert m, 'loc_query not found'
body = m.group(0)
assert 'primaryLanguage' in body, "primaryLanguage field not in loc_query GraphQL"
assert '{ name color }' in body or '{\n' in body and 'name' in body and 'color' in body, "primaryLanguage missing name/color subfields"
print('OK')
```

- [ ] **Step 2: Run it — confirm it fails**

Run: `python3 /tmp/verify_lang_field.py`
Expected: `AssertionError: primaryLanguage field not in loc_query GraphQL`

- [ ] **Step 3: Edit `scripts/today.py:228-254`**

Find the block:

```python
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
```

Insert two lines after `nameWithOwner` (before `isFork`) so the node selection becomes:

```python
                    ... on Repository {
                        nameWithOwner
                        primaryLanguage {
                            name
                            color
                        }
                        isFork
                        parent {
                            nameWithOwner
                        }
                        defaultBranchRef {
```

- [ ] **Step 4: Run verification again — confirm it passes**

Run: `python3 /tmp/verify_lang_field.py`
Expected: `OK`

- [ ] **Step 5: Syntax-check the script**

Run: `python3 -m py_compile scripts/today.py && echo OK`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add scripts/today.py
git commit -m "Add primaryLanguage to loc_query GraphQL selection"
```

---

## Task 2: Add `bar_blocks_for` pure helper

**Files:**
- Modify: `scripts/today.py` — add new function below `flush_cache` (around line 340)

- [ ] **Step 1: Write the failing verification**

Save as `/tmp/verify_bar_blocks.py`:

```python
import importlib.util, sys
spec = importlib.util.spec_from_file_location('today', 'scripts/today.py')
mod = importlib.util.module_from_spec(spec)
# Block side effects from __main__ by setting __name__
mod.__name__ = 'today_import'
sys.modules['today_import'] = mod
# But we don't want it to import env vars on load — set dummies
import os
os.environ.setdefault('ACCESS_TOKEN', 'dummy')
os.environ.setdefault('USER_NAME', 'dummy')
spec.loader.exec_module(mod)

assert mod.bar_blocks_for(100, 100) == 20, f'top language expected 20, got {mod.bar_blocks_for(100, 100)}'
assert mod.bar_blocks_for(50, 100) == 10
assert mod.bar_blocks_for(1, 100) == 1, 'minimum bar for non-zero must be 1'
assert mod.bar_blocks_for(0, 100) == 0
assert mod.bar_blocks_for(100, 0) == 0, 'zero top should yield zero bars (no crash)'
print('OK')
```

- [ ] **Step 2: Run it — confirm it fails**

Run: `python3 /tmp/verify_bar_blocks.py`
Expected: `AttributeError: module 'today' has no attribute 'bar_blocks_for'`

- [ ] **Step 3: Add the helper to `scripts/today.py` directly below the `flush_cache` function**

Locate the end of `flush_cache` (just before `def add_archive():`), insert:

```python
def bar_blocks_for(additions, top_additions):
    """
    Compute Unicode-block bar length for a language given its additions
    and the additions of the top language. Top language gets exactly 20
    blocks; others scale proportionally with a floor of 1 for any
    non-zero value. Returns 0 only when additions is 0 (or top is 0).
    """
    if additions == 0 or top_additions == 0:
        return 0
    if additions >= top_additions:
        return 20
    import math
    return max(1, math.floor(20 * additions / top_additions))
```

- [ ] **Step 4: Run verification again — confirm it passes**

Run: `python3 /tmp/verify_bar_blocks.py`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add scripts/today.py
git commit -m "Add bar_blocks_for helper for language chart bar widths"
```

---

## Task 3: Add `aggregate_languages` pure helper

**Files:**
- Modify: `scripts/today.py` — add new function below `bar_blocks_for`

- [ ] **Step 1: Write the failing verification**

Save as `/tmp/verify_aggregate.py`:

```python
import importlib.util, sys, os
os.environ.setdefault('ACCESS_TOKEN', 'dummy')
os.environ.setdefault('USER_NAME', 'dummy')
spec = importlib.util.spec_from_file_location('today', 'scripts/today.py')
mod = importlib.util.module_from_spec(spec)
mod.__name__ = 'today_import'
sys.modules['today_import'] = mod
spec.loader.exec_module(mod)

edges = [
    {'node': {'nameWithOwner': 'me/a', 'primaryLanguage': {'name': 'Python', 'color': '#3572A5'}}},
    {'node': {'nameWithOwner': 'me/b', 'primaryLanguage': {'name': 'Go', 'color': '#00ADD8'}}},
    {'node': {'nameWithOwner': 'me/c', 'primaryLanguage': {'name': 'Python', 'color': '#3572A5'}}},
    {'node': {'nameWithOwner': 'me/d', 'primaryLanguage': None}},
    {'node': {'nameWithOwner': 'me/e', 'primaryLanguage': {'name': 'Rust', 'color': '#dea584'}}},
]
import hashlib
def h(name): return hashlib.sha256(name.encode()).hexdigest()
# data rows: <hash> <commit_count> <my_commits> <additions> <deletions>
data = [
    f"{h('me/a')} 10 5 1000 100",
    f"{h('me/b')} 10 5 500 50",
    f"{h('me/c')} 10 5 200 20",
    f"{h('me/d')} 10 5 999 99",  # null primaryLanguage — should be skipped
    f"{h('me/e')} 10 5 100 10",
]
buckets = mod.aggregate_languages(edges, data)
# Expected: Python = 1000 + 200 = 1200, Go = 500, Rust = 100. me/d skipped.
names = [b['name'] for b in buckets]
assert names == ['Python', 'Go', 'Rust'], f'wrong order/contents: {names}'
assert buckets[0]['additions'] == 1200
assert buckets[0]['color'] == '#3572A5'
assert buckets[1]['additions'] == 500
assert buckets[2]['additions'] == 100

# Test top-6 cap with Other bucket
edges_many = []
data_many = []
for i, lang in enumerate(['L1','L2','L3','L4','L5','L6','L7','L8']):
    edges_many.append({'node': {'nameWithOwner': f'me/r{i}', 'primaryLanguage': {'name': lang, 'color': f'#{i:06x}'}}})
    data_many.append(f"{h(f'me/r{i}')} 10 5 {1000 - i*10} 0")  # decreasing
b = mod.aggregate_languages(edges_many, data_many)
assert len(b) == 7, f'expected 6 + Other = 7 buckets, got {len(b)}'
assert b[-1]['name'] == 'Other'
assert b[-1]['color'] == '#616e7f', 'Other should use .cc gray'
# Other should sum L7 + L8 = 940 + 930 = 1870
assert b[-1]['additions'] == 1870, f'Other additions {b[-1]["additions"]} != 1870'
print('OK')
```

- [ ] **Step 2: Run it — confirm it fails**

Run: `python3 /tmp/verify_aggregate.py`
Expected: `AttributeError: module 'today' has no attribute 'aggregate_languages'`

- [ ] **Step 3: Add the helper to `scripts/today.py` directly below `bar_blocks_for`**

```python
def aggregate_languages(edges, data):
    """
    Bucket per-repo additions by Repository.primaryLanguage.name. Repos with
    null primaryLanguage are silently skipped (they still count in the total
    LOC widget). Returns a list of dicts ordered by additions descending,
    truncated to top 6 with the remainder collapsed into a single 'Other'
    bucket using .cc gray. Each dict: {'name', 'color', 'additions'}.
    """
    # Build hash -> additions map from cache file rows
    add_by_hash = {}
    for row in data:
        parts = row.split()
        if len(parts) >= 4:
            try:
                add_by_hash[parts[0]] = int(parts[3])
            except ValueError:
                continue
    # Aggregate by language
    totals = {}  # name -> [color, additions]
    for edge in edges:
        node = edge['node']
        lang = node.get('primaryLanguage')
        if not lang or not lang.get('name'):
            continue
        repo_hash = hashlib.sha256(node['nameWithOwner'].encode('utf-8')).hexdigest()
        additions = add_by_hash.get(repo_hash, 0)
        if additions == 0:
            continue
        name = lang['name']
        color = lang.get('color') or '#616e7f'
        if name not in totals:
            totals[name] = [color, 0]
        totals[name][1] += additions
    # Sort by additions desc, top 6, collapse rest into Other
    ranked = sorted(totals.items(), key=lambda kv: kv[1][1], reverse=True)
    top = ranked[:6]
    rest = ranked[6:]
    buckets = [{'name': n, 'color': c, 'additions': a} for n, (c, a) in top]
    if rest:
        buckets.append({'name': 'Other', 'color': '#616e7f', 'additions': sum(a for _, (_, a) in rest)})
    return buckets
```

- [ ] **Step 4: Run verification again — confirm it passes**

Run: `python3 /tmp/verify_aggregate.py`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add scripts/today.py
git commit -m "Add aggregate_languages helper (top 6 + Other bucket)"
```

---

## Task 4: Add `write_language_cache` and `read_language_cache` helpers

**Files:**
- Modify: `scripts/today.py` — add two new functions below `aggregate_languages`

- [ ] **Step 1: Write the failing verification**

Save as `/tmp/verify_lang_cache.py`:

```python
import importlib.util, sys, os, tempfile
os.environ.setdefault('ACCESS_TOKEN', 'dummy')
os.environ.setdefault('USER_NAME', 'dummy')
spec = importlib.util.spec_from_file_location('today', 'scripts/today.py')
mod = importlib.util.module_from_spec(spec)
mod.__name__ = 'today_import'
sys.modules['today_import'] = mod
spec.loader.exec_module(mod)

buckets = [
    {'name': 'Python', 'color': '#3572A5', 'additions': 1200},
    {'name': 'Jupyter Notebook', 'color': '#DA5B0B', 'additions': 800},  # name with space
    {'name': 'Other', 'color': '#616e7f', 'additions': 50},
]
with tempfile.NamedTemporaryFile('w+', suffix='.txt', delete=False) as f:
    path = f.name
mod.write_language_cache(buckets, path)
loaded = mod.read_language_cache(path)
assert loaded == buckets, f'roundtrip failed:\nwrote: {buckets}\nread:  {loaded}'
os.unlink(path)
print('OK')
```

- [ ] **Step 2: Run it — confirm it fails**

Run: `python3 /tmp/verify_lang_cache.py`
Expected: `AttributeError: module 'today' has no attribute 'write_language_cache'`

- [ ] **Step 3: Add both helpers to `scripts/today.py` below `aggregate_languages`**

```python
def write_language_cache(buckets, filename):
    """
    Write the language buckets to a sidecar cache file. Each row:
    <rank> "<language_name>" <hex_color_with_hash> <additions>
    Names are double-quoted so they can contain spaces (e.g. "Jupyter Notebook").
    """
    with open(filename, 'w') as f:
        for rank, b in enumerate(buckets, start=1):
            f.write(f'{rank} "{b["name"]}" {b["color"]} {b["additions"]}\n')


def read_language_cache(filename):
    """
    Read the sidecar cache file back into a list of bucket dicts. Returns
    [] if the file doesn't exist. Format mirrors write_language_cache().
    """
    try:
        with open(filename) as f:
            lines = f.readlines()
    except FileNotFoundError:
        return []
    buckets = []
    for line in lines:
        line = line.rstrip('\n')
        # Format: <rank> "<name>" <color> <additions>
        # Parse by finding the quoted name span
        try:
            first_quote = line.index('"')
            last_quote = line.rindex('"')
            name = line[first_quote + 1:last_quote]
            tail = line[last_quote + 1:].split()
            color = tail[0]
            additions = int(tail[1])
            buckets.append({'name': name, 'color': color, 'additions': additions})
        except (ValueError, IndexError):
            continue
    return buckets
```

- [ ] **Step 4: Run verification again — confirm it passes**

Run: `python3 /tmp/verify_lang_cache.py`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add scripts/today.py
git commit -m "Add language sidecar cache read/write helpers"
```

---

## Task 5: Wire aggregation into `cache_builder` (write sidecar as side effect)

**Files:**
- Modify: `scripts/today.py` — `cache_builder` function (ends around line 321 before `def flush_cache`)

- [ ] **Step 1: Read current `cache_builder` return area**

Open `scripts/today.py` and locate the end of `cache_builder`. The last few lines look like:

```python
    with open(filename, 'w') as f:
        f.writelines(cache_comment)
        f.writelines(data)
    for line in data:
        loc = line.split()
        loc_add += int(loc[3])
        loc_del += int(loc[4])
    return [loc_add, loc_del, loc_add - loc_del, cached]
```

- [ ] **Step 2: Write verification that languages sidecar gets written by cache_builder**

Save as `/tmp/verify_cache_builder_writes_sidecar.py`:

```python
import importlib.util, sys, os, tempfile, hashlib, shutil
os.environ.setdefault('ACCESS_TOKEN', 'dummy')
os.environ.setdefault('USER_NAME', 'verify_user')
spec = importlib.util.spec_from_file_location('today', 'scripts/today.py')
mod = importlib.util.module_from_spec(spec)
mod.__name__ = 'today_import'
sys.modules['today_import'] = mod
spec.loader.exec_module(mod)

# Build minimal edges + write a primed cache file so cache_builder doesn't need to query GitHub
tmpdir = tempfile.mkdtemp()
os.makedirs(os.path.join(tmpdir, 'cache'), exist_ok=True)
os.chdir(tmpdir)

edges = [
    {'node': {'nameWithOwner': 'me/a', 'primaryLanguage': {'name': 'Python', 'color': '#3572A5'},
              'defaultBranchRef': {'target': {'history': {'totalCount': 10}}}}},
    {'node': {'nameWithOwner': 'me/b', 'primaryLanguage': {'name': 'Go', 'color': '#00ADD8'},
              'defaultBranchRef': {'target': {'history': {'totalCount': 5}}}}},
]
def h(name): return hashlib.sha256(name.encode()).hexdigest()
user_hash = hashlib.sha256('verify_user'.encode()).hexdigest()
cache_path = f'cache/{user_hash}.txt'
with open(cache_path, 'w') as f:
    f.write(f'{h("me/a")} 10 5 1000 100\n')
    f.write(f'{h("me/b")} 5 3 500 50\n')

result = mod.cache_builder(edges, 0, False)
assert result[0] == 1500, f'loc_add expected 1500 got {result[0]}'

# Sidecar should exist
sidecar_path = f'cache/{user_hash}_langs.txt'
assert os.path.exists(sidecar_path), f'sidecar {sidecar_path} not written'
buckets = mod.read_language_cache(sidecar_path)
names = [b['name'] for b in buckets]
assert names == ['Python', 'Go'], f'unexpected sidecar contents: {names}'
print('OK')
```

- [ ] **Step 3: Run it — confirm it fails**

Run: `python3 /tmp/verify_cache_builder_writes_sidecar.py`
Expected: `AssertionError: sidecar cache/.../_langs.txt not written`

- [ ] **Step 4: Edit `cache_builder` in `scripts/today.py`** — replace the final block

Replace:

```python
    with open(filename, 'w') as f:
        f.writelines(cache_comment)
        f.writelines(data)
    for line in data:
        loc = line.split()
        loc_add += int(loc[3])
        loc_del += int(loc[4])
    return [loc_add, loc_del, loc_add - loc_del, cached]
```

With:

```python
    with open(filename, 'w') as f:
        f.writelines(cache_comment)
        f.writelines(data)
    # Aggregate per-language additions and write the languages sidecar so
    # render_languages_svg can be called from __main__ without re-reading edges.
    language_buckets = aggregate_languages(edges, data)
    langs_filename = filename[:-4] + '_langs.txt'  # cache/<hash>.txt -> cache/<hash>_langs.txt
    write_language_cache(language_buckets, langs_filename)
    for line in data:
        loc = line.split()
        loc_add += int(loc[3])
        loc_del += int(loc[4])
    return [loc_add, loc_del, loc_add - loc_del, cached]
```

- [ ] **Step 5: Run verification again — confirm it passes**

Run: `python3 /tmp/verify_cache_builder_writes_sidecar.py`
Expected: `OK`

- [ ] **Step 6: Syntax-check the script**

Run: `python3 -m py_compile scripts/today.py && echo OK`
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add scripts/today.py
git commit -m "Write languages sidecar as cache_builder side effect"
```

---

## Task 6: Add `render_languages_svg` function

**Files:**
- Modify: `scripts/today.py` — add new function below `read_language_cache`

- [ ] **Step 1: Write the failing verification**

Save as `/tmp/verify_render_svg.py`:

```python
import importlib.util, sys, os, tempfile
os.environ.setdefault('ACCESS_TOKEN', 'dummy')
os.environ.setdefault('USER_NAME', 'dummy')
spec = importlib.util.spec_from_file_location('today', 'scripts/today.py')
mod = importlib.util.module_from_spec(spec)
mod.__name__ = 'today_import'
sys.modules['today_import'] = mod
spec.loader.exec_module(mod)

buckets = [
    {'name': 'Python', 'color': '#3572A5', 'additions': 1200},
    {'name': 'Go', 'color': '#00ADD8', 'additions': 600},
    {'name': 'Other', 'color': '#616e7f', 'additions': 100},
]
with tempfile.NamedTemporaryFile('w', suffix='.svg', delete=False) as f:
    out_path = f.name
mod.render_languages_svg(buckets, 'dark', out_path)
with open(out_path) as f:
    svg = f.read()

assert svg.startswith("<?xml"), 'SVG should start with XML declaration'
assert 'width="850px"' in svg and 'height="255px"' in svg, '850x255 dimensions required'
assert '#161b22' in svg, 'dark mode background color must be present'
assert 'Python' in svg and 'Go' in svg and 'Other' in svg, 'language names missing'
assert '#3572A5' in svg, "Python's GitHub color must appear (as bar fill)"
assert '#00ADD8' in svg, "Go's GitHub color must appear"
assert '#616e7f' in svg, "Other bucket should use .cc gray for bar"
# Top language gets 20 blocks
assert '█' * 20 in svg, 'top language must have 20 full-block bar chars'

# Light mode variant should swap the background
with tempfile.NamedTemporaryFile('w', suffix='.svg', delete=False) as f:
    out_light = f.name
mod.render_languages_svg(buckets, 'light', out_light)
with open(out_light) as f:
    svg_light = f.read()
assert '#fffefe' in svg_light or '#ffffff' in svg_light or '#f6f8fa' in svg_light, \
    'light mode background must differ from dark'

# Empty buckets case
with tempfile.NamedTemporaryFile('w', suffix='.svg', delete=False) as f:
    out_empty = f.name
mod.render_languages_svg([], 'dark', out_empty)
with open(out_empty) as f:
    svg_empty = f.read()
assert 'no language data' in svg_empty, 'empty buckets should render fallback message'
os.unlink(out_path); os.unlink(out_light); os.unlink(out_empty)
print('OK')
```

- [ ] **Step 2: Verify what light-mode background color the existing SVG uses**

Run: `grep -E 'fill="#[a-fA-F0-9]+"' compact/light_mode_simple.svg | head -3`
Note the hex color used in the outer `<rect>` (the page background). Use that exact value as the light mode background in the implementation below.

- [ ] **Step 3: Run verification — confirm it fails**

Run: `python3 /tmp/verify_render_svg.py`
Expected: `AttributeError: module 'today' has no attribute 'render_languages_svg'`

- [ ] **Step 4: Add the function to `scripts/today.py` below `read_language_cache`**

Replace `LIGHT_BG_HEX` and `LIGHT_TEXT_HEX` placeholders below with the values you found in Step 2 (looking at the existing `compact/light_mode_simple.svg` `<rect fill=…>` and the main `<text fill=…>`):

```python
def render_languages_svg(buckets, mode, output_path):
    """
    Render the languages-by-LOC bar chart SVG, matching the aesthetic of
    compact/*_simple.svg. mode is 'dark' or 'light'. buckets is the list
    of dicts from aggregate_languages() or read_language_cache(). If
    buckets is empty, renders a fallback row.
    """
    if mode == 'dark':
        bg = '#161b22'
        text = '#c9d1d9'
    else:
        bg = 'LIGHT_BG_HEX'      # replace with hex from compact/light_mode_simple.svg <rect>
        text = 'LIGHT_TEXT_HEX'  # replace with hex from compact/light_mode_simple.svg <text fill>

    total = sum(b['additions'] for b in buckets) or 1
    top = max((b['additions'] for b in buckets), default=0)

    header = '<?xml version=\'1.0\' encoding=\'UTF-8\'?>\n'
    svg_open = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'font-family="ConsolasFallback,Consolas,monospace" '
        'width="850px" height="255px" font-size="16px">\n'
    )
    style = (
        '<style>\n'
        '@font-face {\n'
        "src: local('Consolas'), local('Consolas Bold');\n"
        "font-family: 'ConsolasFallback';\n"
        'font-display: swap;\n'
        '-webkit-size-adjust: 109%;\n'
        'size-adjust: 109%;\n'
        '}\n'
        '.key {fill: #ffa657;}\n'
        '.value {fill: #a5d6ff;}\n'
        '.cc {fill: #616e7f;}\n'
        'text, tspan {white-space: pre;}\n'
        '</style>\n'
    )
    rect = f'<rect width="850" height="255px" fill="{bg}" rx="15"/>\n'

    # Right-panel header at the same y-offset as the existing GitHub Stats header
    rows = [f'<text x="15" y="30" fill="{text}">']
    rows.append('<tspan x="15" y="50">- Languages by LOC</tspan> ————————————————————————————————————————————————')

    if not buckets:
        rows.append('<tspan x="15" y="80" class="cc">. (no language data)</tspan>')
    else:
        y = 80
        for b in buckets:
            blocks = bar_blocks_for(b['additions'], top)
            bar = '█' * blocks + ' ' * (20 - blocks)
            pct = round(100 * b['additions'] / total)
            # Abbreviate count: 1234567 -> 1.2M, 12345 -> 12K, 999 -> 999
            n = b['additions']
            if n >= 1_000_000:
                count_str = f'{n / 1_000_000:.1f}M'
            elif n >= 1_000:
                count_str = f'{n / 1_000:.0f}K'
            else:
                count_str = str(n)
            # Pad name to 14 chars so bars line up
            name_padded = b['name'][:14].ljust(14)
            rows.append(
                f'<tspan x="15" y="{y}" class="cc">. </tspan>'
                f'<tspan class="key">{name_padded}</tspan>'
                f'<tspan> </tspan>'
                f'<tspan fill="{b["color"]}">{bar}</tspan>'
                f'<tspan class="value"> {count_str}</tspan>'
                f'<tspan class="cc"> ({pct}%)</tspan>'
            )
            y += 20

    rows.append('</text>')
    body = '\n'.join(rows) + '\n</svg>\n'
    with open(output_path, 'w') as f:
        f.write(header + svg_open + style + rect + body)
```

- [ ] **Step 5: Run verification — confirm it passes**

Run: `python3 /tmp/verify_render_svg.py`
Expected: `OK`

- [ ] **Step 6: Syntax-check + visually open the test output**

Run: `python3 -m py_compile scripts/today.py && echo OK`

Then render and open a sample SVG to eyeball:

```bash
python3 -c "
import sys
sys.path.insert(0, 'scripts')
import os
os.environ.setdefault('ACCESS_TOKEN', 'dummy')
os.environ.setdefault('USER_NAME', 'dummy')
import importlib.util
spec = importlib.util.spec_from_file_location('today', 'scripts/today.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
buckets = [
    {'name': 'Python', 'color': '#3572A5', 'additions': 1200000},
    {'name': 'TypeScript', 'color': '#3178c6', 'additions': 600000},
    {'name': 'Go', 'color': '#00ADD8', 'additions': 200000},
    {'name': 'Other', 'color': '#616e7f', 'additions': 90000},
]
mod.render_languages_svg(buckets, 'dark', '/tmp/preview_dark.svg')
mod.render_languages_svg(buckets, 'light', '/tmp/preview_light.svg')
print('wrote /tmp/preview_dark.svg and /tmp/preview_light.svg')
"
open /tmp/preview_dark.svg /tmp/preview_light.svg
```

Visually verify: bars match the dark/light aesthetic, language colors are correct, percentages add up to 100% (±1%), no overflow past 850×255.

- [ ] **Step 7: Commit**

```bash
git add scripts/today.py
git commit -m "Add render_languages_svg with dark/light modes"
```

---

## Task 7: Wire `render_languages_svg` into `__main__`

**Files:**
- Modify: `scripts/today.py:625-628` (the four existing `svg_overwrite` calls)

- [ ] **Step 1: Edit the block to add two render_languages_svg calls**

After line 628 (the last `svg_overwrite('compact/light_mode_simple.svg', ...)` line), insert:

```python
    # Languages-by-LOC chart, paired with the compact stats SVGs above
    langs_filename = 'cache/' + hashlib.sha256(USER_NAME.encode('utf-8')).hexdigest() + '_langs.txt'
    language_buckets = read_language_cache(langs_filename)
    render_languages_svg(language_buckets, 'dark', 'compact/dark_mode_languages.svg')
    render_languages_svg(language_buckets, 'light', 'compact/light_mode_languages.svg')
```

- [ ] **Step 2: Syntax-check the script**

Run: `python3 -m py_compile scripts/today.py && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add scripts/today.py
git commit -m "Render languages SVGs in __main__ alongside existing widgets"
```

---

## Task 8: Update `README.md` with second `<picture>` block

**Files:**
- Modify: `README.md:1-6`

- [ ] **Step 1: Read current README top**

Confirm lines 1-6 are the existing `<picture>` block.

- [ ] **Step 2: Add a second `<picture>` block immediately under**

Insert after line 6 (before the blank line 7):

```markdown
<a href="https://github.com/Technical-1/Technical-1">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Technical-1/Technical-1/main/compact/dark_mode_languages.svg">
    <img alt="Jacob Kanfer's Top Languages by LOC" src="https://raw.githubusercontent.com/Technical-1/Technical-1/main/compact/light_mode_languages.svg">
  </picture>
</a>
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Add languages-by-LOC SVG to README"
```

---

## Task 9: Push and verify end-to-end

**Files:** none

- [ ] **Step 1: Push**

Run: `git push origin main` (or via SSH if the workflow file scope blocks: `git push git@github.com:Technical-1/Technical-1.git main`).

- [ ] **Step 2: Wait for the workflow to complete**

Run: `gh run watch $(gh run list --workflow=build.yaml --limit 1 --json databaseId --jq '.[0].databaseId') --exit-status`
Expected: exit 0 (success) in ~1-2 minutes.

- [ ] **Step 3: Pull the bot's commit and inspect**

```bash
git pull --ff-only origin main
ls compact/*_languages.svg
cat cache/*_langs.txt
```

Expected: both new SVG files exist; the sidecar has one row per top-6 language plus optional Other.

- [ ] **Step 4: Visually verify both SVGs**

```bash
open compact/dark_mode_languages.svg compact/light_mode_languages.svg
```

Check: identical framing to compact_simple.svg, language colors present, bars line up, percentages reasonable, dark/light backgrounds correct.

- [ ] **Step 5: Visually verify the README on GitHub**

Open `https://github.com/Technical-1/Technical-1` in a browser; confirm the new SVG appears below the existing one, prefers-color-scheme switching works for both.

---

## Self-Review

**Spec coverage:**
- Visual spec (850×255, palette, fonts) — Task 6 ✓
- Files created/modified — Tasks 1, 5, 6, 7, 8 ✓
- Data flow (primaryLanguage in query → aggregate → sidecar → render) — Tasks 1, 3, 5, 7 ✓
- Sidecar format (quoted names) — Task 4 ✓
- Bar-width calc — Task 2 ✓
- Edge cases (null primaryLanguage, zero total) — Tasks 3, 6 ✓
- Workflow integration (no changes needed, generates alongside existing) — Task 7 + Task 9 verification ✓
- Top 6 + Other — Task 3 ✓
- GitHub language colors — Task 6 ✓
- Light mode variant — Task 6 + Step 2 ✓

**Placeholder scan:**
- `LIGHT_BG_HEX` / `LIGHT_TEXT_HEX` in Task 6 are placeholders — but Step 2 explicitly instructs reading them from the existing light SVG. This is a deliberate "look it up" not a "TBD." Acceptable.
- No other TBD/TODO/"handle edge cases"/etc. found.

**Type consistency:**
- `aggregate_languages` returns `list[dict]` with keys `name`, `color`, `additions` — same shape consumed by `write_language_cache`, `read_language_cache`, and `render_languages_svg`. ✓
- `bar_blocks_for(additions, top_additions)` signature consistent between definition (Task 2) and call site (Task 6). ✓
- `cache_builder` return tuple unchanged — only side effect added (sidecar write) — no breakage downstream. ✓

**Scope:** Single feature, single file modified (+ one README line), no infrastructure changes. Single PR. ✓
