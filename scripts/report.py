"""
Reads results/*.json and prints markdown tables ready to paste into README.md.

Usage:
    python scripts/report.py
"""
import glob
import json
import os

from tabulate import tabulate

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")


def load_all(prefix):
    out = {}
    for path in glob.glob(os.path.join(RESULTS_DIR, f"{prefix}_*.json")):
        platform = os.path.basename(path).replace(f"{prefix}_", "").replace(".json", "")
        with open(path) as f:
            out[platform] = json.load(f)
    return out


def fmt(v):
    return f"{v:.2f}" if isinstance(v, float) else str(v)


def main():
    loads = load_all("load")
    benches = load_all("bench")
    platforms = sorted(set(loads) | set(benches))

    if not platforms:
        print("No results found yet. Run loader.py and benchmark.py first.")
        return

    print("\n## Data Loading\n")
    rows = []
    for p in platforms:
        l = loads.get(p, {})
        rows.append([p, l.get("nodes_loaded"), l.get("relationships_loaded"),
                     l.get("nodes_per_second"), l.get("relationships_per_second"),
                     l.get("wall_clock_seconds")])
    print(tabulate(rows, headers=["Platform", "Nodes", "Rels", "Nodes/s", "Rels/s", "Wall clock (s)"], tablefmt="github"))

    print("\n## Traversals (p50 / p95 ms)\n")
    rows = []
    for p in platforms:
        t = benches.get(p, {}).get("traversals_ms", {})
        row = [p]
        for hop in ["1_hop", "2_hop", "3_hop"]:
            d = t.get(hop, {})
            row.append(f"{fmt(d.get('50'))} / {fmt(d.get('95'))}")
        rows.append(row)
    print(tabulate(rows, headers=["Platform", "1-hop", "2-hop", "3-hop"], tablefmt="github"))

    print("\n## Lookups (p50 / p95 ms)\n")
    rows = []
    for p in platforms:
        l = benches.get(p, {}).get("lookups_ms", {})
        point = l.get("point_lookup", {})
        idx = l.get("indexed_lookup", {})
        rows.append([p, f"{fmt(point.get('50'))} / {fmt(point.get('95'))}",
                     f"{fmt(idx.get('50'))} / {fmt(idx.get('95'))}"])
    print(tabulate(rows, headers=["Platform", "Point lookup", "Indexed lookup"], tablefmt="github"))

    print("\n## Aggregation (p50 / p95 ms)\n")
    rows = []
    for p in platforms:
        a = benches.get(p, {}).get("aggregation_ms", {}).get("group_by_out_degree_top100", {})
        rows.append([p, f"{fmt(a.get('50'))} / {fmt(a.get('95'))}"])
    print(tabulate(rows, headers=["Platform", "Group-by top-100"], tablefmt="github"))

    print("\n## Mixed Workload\n")
    rows = []
    for p in platforms:
        m = benches.get(p, {}).get("mixed_workload", {})
        rows.append([p, m.get("concurrency"), m.get("read_write_mix"), m.get("queries_per_second")])
    print(tabulate(rows, headers=["Platform", "Concurrency", "R/W mix", "QPS"], tablefmt="github"))
    print()


if __name__ == "__main__":
    main()
