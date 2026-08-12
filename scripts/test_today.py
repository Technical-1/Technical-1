"""
Regression tests for today.py's GraphQL edge handling.

Run with: python scripts/test_today.py

No test framework is used on purpose; cache/requirements.txt is kept to the
runtime deps the workflow actually needs, so these are plain asserts.

Context: the scheduled README build failed 20 nights running (2026-07-23 through
2026-08-11) with `TypeError: 'NoneType' object is not subscriptable` because
GitHub's GraphQL API returns edges whose `node` is null for repositories the
token cannot read. These tests pin that behaviour so it cannot regress.
"""
import os
import sys

os.environ.setdefault('ACCESS_TOKEN', 'fake-token-for-tests')
os.environ.setdefault('USER_NAME', 'fake-user-for-tests')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import today  # noqa: E402


def edge(name_with_owner, is_fork=False, parent=None, stars=0):
    """Build an edge shaped like the graph_repos_stars query returns."""
    return {'node': {
        'nameWithOwner': name_with_owner,
        'isFork': is_fork,
        'parent': {'nameWithOwner': parent} if parent else None,
        'stargazers': {'totalCount': stars},
    }}


TESTS = []


def test(fn):
    TESTS.append(fn)
    return fn


@test
def filter_owned_forks_skips_null_nodes():
    """A null node (repo the token cannot read) must not crash the filter."""
    edges = [
        edge('Technical-1/All-About-Me'),
        {'node': None},  # inaccessible org repo
        edge('Technical-1/Technical-1'),
    ]
    result = today.filter_owned_forks(edges)
    names = [e['node']['nameWithOwner'] for e in result]
    assert names == ['Technical-1/All-About-Me', 'Technical-1/Technical-1'], names


@test
def stars_counter_skips_null_nodes():
    """stars_counter has the same latent crash on a null node."""
    edges = [
        edge('Technical-1/a', stars=3),
        {'node': None},
        edge('Technical-1/b', stars=4),
    ]
    assert today.stars_counter(edges) == 7


@test
def filter_owned_forks_drops_fork_whose_parent_is_in_list():
    """Regression guard: the original dedupe behaviour must survive the fix."""
    edges = [
        edge('upstream/thing'),
        edge('Technical-1/thing', is_fork=True, parent='upstream/thing'),
    ]
    result = today.filter_owned_forks(edges)
    names = [e['node']['nameWithOwner'] for e in result]
    assert names == ['upstream/thing'], names


@test
def filter_owned_forks_keeps_fork_whose_parent_is_absent():
    """Regression guard: forks of repos not in the list still count."""
    edges = [
        edge('Technical-1/other'),
        edge('Technical-1/thing', is_fork=True, parent='someone-else/thing'),
    ]
    result = today.filter_owned_forks(edges)
    names = [e['node']['nameWithOwner'] for e in result]
    assert names == ['Technical-1/other', 'Technical-1/thing'], names


@test
def filter_owned_forks_handles_all_null_page():
    """Degenerate case: every node null should yield an empty list, not a crash."""
    assert today.filter_owned_forks([{'node': None}, {'node': None}]) == []


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError('not json')
        return self._payload


def capture_warnings(payload):
    """Run warn_on_graphql_errors against a payload and return printed lines."""
    import io
    import contextlib
    today.GRAPHQL_WARNINGS_SEEN.clear()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        today.warn_on_graphql_errors('test_func', FakeResponse(payload))
    return buf.getvalue().splitlines()


@test
def warn_on_graphql_errors_reports_forbidden_repo():
    """A partial response must announce itself in the log."""
    lines = capture_warnings({
        'data': {'user': {'repositories': {'edges': [{'node': None}]}}},
        'errors': [{
            'type': 'FORBIDDEN',
            'path': ['user', 'repositories', 'edges', 0, 'node'],
            'message': 'Resource not accessible by personal access token',
        }],
    })
    assert any('FORBIDDEN' in l for l in lines), lines
    assert any('understated' in l for l in lines), lines


@test
def warn_on_graphql_errors_dedupes_repeated_errors():
    """Pagination must not print the same error hundreds of times."""
    payload = {'errors': [{'type': 'NOT_FOUND', 'path': ['user'], 'message': 'gone'}]}
    first = capture_warnings(payload)
    # second call in the same process, cache intentionally not cleared
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        today.warn_on_graphql_errors('test_func', FakeResponse(payload))
    assert len(first) > 0
    assert buf.getvalue() == '', buf.getvalue()


@test
def warn_on_graphql_errors_silent_on_clean_response():
    """A healthy response must stay quiet."""
    assert capture_warnings({'data': {'user': {}}}) == []


@test
def warn_on_graphql_errors_survives_non_json_body():
    """A non-JSON body must not raise from inside the warning path."""
    assert capture_warnings(None) == []


if __name__ == '__main__':
    failed = 0
    for t in TESTS:
        try:
            t()
            print(f'  PASS  {t.__name__}')
        except Exception as e:
            failed += 1
            print(f'  FAIL  {t.__name__}: {type(e).__name__}: {e}')
    print(f'\n{len(TESTS) - failed}/{len(TESTS)} passed')
    sys.exit(1 if failed else 0)
