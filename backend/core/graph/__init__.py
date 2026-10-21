"""Graph queries over `accounts_connection`: recursive SQL for paths, networkx for cycles.

Connections are stored once with member_a < member_b; here they are treated as undirected.
"""

import networkx as nx
from django.db import connection

_NEIGHBOURS_SQL = """
WITH RECURSIVE edges AS (
    SELECT member_a_id AS a, member_b_id AS b, strength FROM accounts_connection
    UNION ALL
    SELECT member_b_id, member_a_id, strength FROM accounts_connection
),
walk AS (
    SELECT b AS node, 1 AS hops, ARRAY[%(start)s, b] AS path, strength AS weakest
    FROM edges WHERE a = %(start)s
    UNION ALL
    SELECT e.b, w.hops + 1, w.path || e.b, LEAST(w.weakest, e.strength)
    FROM walk w JOIN edges e ON e.a = w.node
    WHERE w.hops < %(max_hops)s AND NOT e.b = ANY(w.path)
)
SELECT DISTINCT ON (node) node, hops, path, weakest
FROM walk ORDER BY node, hops, weakest DESC
"""


def neighbours(member_id: int, max_hops: int = 2) -> dict[int, dict]:
    """Members reachable in <= max_hops: {id: {"hops", "path", "strength"}} (strength = weakest link on the best path: fewest hops, then strongest)."""
    with connection.cursor() as cur:
        cur.execute(_NEIGHBOURS_SQL, {"start": member_id, "max_hops": max_hops})
        return {n: {"hops": h, "path": p, "strength": s} for n, h, p, s in cur.fetchall() if n != member_id}


def best_path(source: int, target: int, max_hops: int = 2) -> list[int] | None:
    """Strongest shortest path source -> target (member ids, inclusive), or None."""
    found = neighbours(source, max_hops).get(target)
    return found["path"] if found else None


def find_cycles(edges: list[tuple[int, int]], length: int = 3) -> list[list[int]]:
    """Directed cycles of exactly `length` nodes, each returned once, starting at its smallest node."""
    g = nx.DiGraph(edges)
    seen: set[tuple[int, ...]] = set()
    out = []
    for cyc in nx.simple_cycles(g, length_bound=length):
        if len(cyc) != length:
            continue
        i = cyc.index(min(cyc))
        canon = tuple(cyc[i:] + cyc[:i])
        if canon not in seen:
            seen.add(canon)
            out.append(list(canon))
    return sorted(out)
