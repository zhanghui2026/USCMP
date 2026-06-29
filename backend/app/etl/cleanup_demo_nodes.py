"""Remove demo/test nodes from Neo4j."""
from app.db.neo4j import run_cypher


def cleanup():
    find_query = """
    MATCH (n)
    WHERE n.display_name CONTAINS "Demo"
       OR n.canonical_name CONTAINS "Demo"
       OR n.id CONTAINS "demo"
    RETURN n.id AS node_id, labels(n) AS labels, n.display_name AS name
    """
    nodes = list(run_cypher(find_query) or [])
    print(f"Found {len(nodes)} demo nodes:")
    for n in nodes:
        print(f"  {n.get('node_id')}: {n.get('labels')} ({n.get('name')})")

    if nodes:
        del_query = """
        MATCH (n)
        WHERE n.display_name CONTAINS "Demo"
           OR n.canonical_name CONTAINS "Demo"
           OR n.id CONTAINS "demo"
        DETACH DELETE n
        """
        run_cypher(del_query)
        print(f"Deleted {len(nodes)} demo nodes")

    count_query = "MATCH (n:Person) RETURN count(n) AS cnt"
    result = list(run_cypher(count_query) or [])
    total = result[0]["cnt"] if result else 0
    print(f"Remaining Person nodes: {total}")


if __name__ == "__main__":
    cleanup()
