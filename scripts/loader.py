"""
Loads the email-Enron edge list into a target platform (CognoDB or Aura)
using batched UNWIND writes via the official Neo4j driver, and records
ingest throughput.

Usage:
    python scripts/loader.py --platform cognodb
    python scripts/loader.py --platform aura
"""
import argparse
import json
import os
import time

from common import get_driver, PLATFORMS

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "email-Enron.txt")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
BATCH_SIZE = 1000

CONSTRAINT = "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE"

LOAD_QUERY = """
UNWIND $rows AS row
MERGE (a:Person {id: row.src})
MERGE (b:Person {id: row.dst})
MERGE (a)-[:EMAILED]->(b)
"""


def read_edges():
    with open(DATA_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) != 2:
                continue
            src, dst = parts
            yield int(src), int(dst)

def batched(iterable, size):
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", required=True, choices=list(PLATFORMS.keys()))
    args = ap.parse_args()

    if not os.path.exists(DATA_PATH):
        raise SystemExit("Dataset not found. Run: python scripts/download_dataset.py")

    driver = get_driver(args.platform)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    node_ids = set()
    edge_count = 0

    with driver.session() as session:
        session.run(CONSTRAINT).consume()

        start = time.perf_counter()
        for batch in batched(read_edges(), BATCH_SIZE):
            rows = [{"src": s, "dst": d} for s, d in batch]
            session.run(LOAD_QUERY, rows=rows).consume()
            edge_count += len(batch)
            for s, d in batch:
                node_ids.add(s)
                node_ids.add(d)
        elapsed = time.perf_counter() - start

    result = {
        "platform": args.platform,
        "nodes_loaded": len(node_ids),
        "relationships_loaded": edge_count,
        "wall_clock_seconds": round(elapsed, 2),
        "nodes_per_second": round(len(node_ids) / elapsed, 1),
        "relationships_per_second": round(edge_count / elapsed, 1),
    }

    out_path = os.path.join(RESULTS_DIR, f"load_{args.platform}.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()
