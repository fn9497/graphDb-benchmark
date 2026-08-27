"""
Runs the required benchmark workloads against a target platform and writes
a results JSON file that scripts/report.py turns into README tables.

Usage:
    python scripts/benchmark.py --platform cognodb
    python scripts/benchmark.py --platform aura
"""
import argparse
import json
import os
import random
import time
import concurrent.futures as cf

from common import get_driver, PLATFORMS, percentiles, run_timed_query

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

ITERATIONS = int(os.getenv("BENCH_ITERATIONS", "20"))
CONCURRENCY = int(os.getenv("BENCH_CONCURRENCY", "10"))
MIXED_DURATION_S = 20

HOP_QUERIES = {
    1: "MATCH (a:Person {id: $id})-[:EMAILED]->(b) RETURN count(b)",
    2: "MATCH (a:Person {id: $id})-[:EMAILED]->()-[:EMAILED]->(b) RETURN count(b)",
    3: "MATCH (a:Person {id: $id})-[:EMAILED]->()-[:EMAILED]->()-[:EMAILED]->(b) RETURN count(b)",
}
POINT_LOOKUP_Q = "MATCH (p:Person {id: $id}) RETURN p"
INDEXED_LOOKUP_Q = "MATCH (p:Person) WHERE p.id = $id RETURN p"  # uses the unique constraint index
AGGREGATION_Q = "MATCH (p:Person)-[:EMAILED]->() RETURN p.id AS id, count(*) AS out_degree ORDER BY out_degree DESC LIMIT 100"

MIXED_READ_Q = "MATCH (a:Person {id: $id})-[:EMAILED]->(b) RETURN count(b)"
MIXED_WRITE_Q = "MATCH (a:Person {id: $id}) SET a.last_seen = timestamp()"


def sample_ids(driver, n=200):
    with driver.session() as session:
        recs = session.run(
            "MATCH (p:Person) RETURN p.id AS id ORDER BY rand() LIMIT $n", n=n
        )
        return [r["id"] for r in recs]


def warm_up(driver, ids, rounds=5):
    with driver.session() as session:
        for _ in range(rounds):
            for pid in ids[:10]:
                session.run(HOP_QUERIES[1], id=pid).consume()


def bench_traversals(driver, ids):
    out = {}
    with driver.session() as session:
        for hop, q in HOP_QUERIES.items():
            lats = []
            for i in range(ITERATIONS):
                pid = ids[i % len(ids)]
                lats += run_timed_query(session, q, {"id": pid}, n=1)
            out[f"{hop}_hop"] = percentiles(lats)
    return out


def bench_lookups(driver, ids):
    out = {}
    with driver.session() as session:
        lats = []
        for i in range(ITERATIONS):
            lats += run_timed_query(session, POINT_LOOKUP_Q, {"id": ids[i % len(ids)]}, n=1)
        out["point_lookup"] = percentiles(lats)

        lats = []
        for i in range(ITERATIONS):
            lats += run_timed_query(session, INDEXED_LOOKUP_Q, {"id": ids[i % len(ids)]}, n=1)
        out["indexed_lookup"] = percentiles(lats)
    return out


def bench_aggregation(driver):
    with driver.session() as session:
        lats = run_timed_query(session, AGGREGATION_Q, n=ITERATIONS)
    return {"group_by_out_degree_top100": percentiles(lats)}


def _mixed_worker(driver, ids, stop_at, read_write_ratio=0.8):
    count = 0
    with driver.session() as session:
        while time.perf_counter() < stop_at:
            pid = random.choice(ids)
            if random.random() < read_write_ratio:
                session.run(MIXED_READ_Q, id=pid).consume()
            else:
                session.run(MIXED_WRITE_Q, id=pid).consume()
            count += 1
    return count


def bench_mixed(driver, ids):
    stop_at = time.perf_counter() + MIXED_DURATION_S
    with cf.ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futures = [ex.submit(_mixed_worker, driver, ids, stop_at) for _ in range(CONCURRENCY)]
        totals = [f.result() for f in futures]
    total_ops = sum(totals)
    qps = total_ops / MIXED_DURATION_S
    return {
        "concurrency": CONCURRENCY,
        "read_write_mix": "80/20",
        "duration_seconds": MIXED_DURATION_S,
        "total_ops": total_ops,
        "queries_per_second": round(qps, 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", required=True, choices=list(PLATFORMS.keys()))
    args = ap.parse_args()

    driver = get_driver(args.platform)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    print("Sampling start nodes...")
    ids = sample_ids(driver, n=max(50, ITERATIONS))

    print("Warming up...")
    warm_up(driver, ids)

    print("Running traversal benchmarks...")
    traversals = bench_traversals(driver, ids)

    print("Running lookup benchmarks...")
    lookups = bench_lookups(driver, ids)

    print("Running aggregation benchmark...")
    aggregation = bench_aggregation(driver)

    print(f"Running mixed workload ({CONCURRENCY} concurrent clients, {MIXED_DURATION_S}s)...")
    mixed = bench_mixed(driver, ids)

    result = {
        "platform": args.platform,
        "iterations_per_workload": ITERATIONS,
        "advertised_specs": PLATFORMS[args.platform]["advertised_specs"],
        "traversals_ms": traversals,
        "lookups_ms": lookups,
        "aggregation_ms": aggregation,
        "mixed_workload": mixed,
    }

    out_path = os.path.join(RESULTS_DIR, f"bench_{args.platform}.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()
