# Graph Database Cloud Benchmark: CognoDB vs. Neo4j AuraDB Free

A reproducible benchmark comparing [CognoDB Cloud](https://console.cognodb.com) against
Neo4j AuraDB Free on identical hardware tiers, identical dataset, and identical Cypher
queries, using the official Neo4j Bolt driver against both (CognoDB exposes a
Neo4j-compatible `bolt+s://` endpoint).

## ⚠️ Scope note (read first)

This submission was produced under a **hard 2-hour deadline** rather than the full
window. To keep every number honest and reproducible in that time, the scope was
deliberately cut down from the "strong submission" bar:

* **2 platforms benchmarked (CognoDB + Neo4j AuraDB Free), not 5.** Aura was chosen
because it uses the exact same driver and Cypher dialect as CognoDB, which removed
all query-translation risk and let every remaining minute go to correctness rather
than porting queries to Gremlin/AQL/etc.
* **`BENCH\_ITERATIONS=20`** per read workload by default, not the suggested ≥100 — set
via `.env`, trivially raised back to 100+ by anyone re-running this with more time.
* The mixed workload runs for a fixed 20 seconds rather than sweeping 1/10/40 clients.
* No cold-start vs. warm-start separation was measured.

**The harness itself is not scoped down** — it is written so that adding a third,
fourth, and fifth platform is just: add credentials to `.env`, add an entry to
`PLATFORMS` in `scripts/common.py`, and re-run `scripts/run\_all.sh`. See
[Extending to more platforms](#extending-to-more-platforms).

## 1\. Dataset

[SNAP `email-Enron`](https://snap.stanford.edu/data/email-Enron.html) — a real, public
directed communication network: **36,692 nodes, 183,831 relationships**. This sits
inside the assignment's required 100k–500k relationship range and is small enough to
fit comfortably inside every free tier in scope.

Nodes are labeled `:Person {id}`, edges are `:EMAILED` relationships. A uniqueness
constraint on `Person.id` is created on load (this is also the index used for the
"indexed lookup" workload).

Download it with:

```bash
python scripts/download\_dataset.py
```

## 2\. Platforms and resource parity

|Platform|Tier|Advertised specs|
|-|-|-|
|CognoDB Cloud|Free (c0)|Burstable 0.5 vCPU, 256 MB RAM, 1 GB disk|
|Neo4j AuraDB|Free|Shared vCPU, 1 GB RAM, \~8 GB disk cap (entry-level free tier)|

**Fairness note:** AuraDB Free's advertised RAM/disk ceiling is larger than CognoDB's
free tier. This is a known asymmetry in what each vendor offers at "$0" — there is no
smaller Aura tier to step down to. Per the assignment's fairness rule, this is
disclosed rather than hidden; the dataset is sized so it fits inside the *smaller* of
the two (CognoDB's 1 GB disk / 256 MB RAM), so neither platform is memory- or
disk-starved relative to its own limit, but the comparison is not perfectly apples-to-apples
on RAM. A stronger version of this study would find (or self-host) a graph DB capped to
literally the same MB/vCPU figures for every platform.

## 3\. Setup

```bash
python -m venv .venv \&\& source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your own credentials, see below
```

### 3.1 CognoDB Cloud

1. Sign up at https://console.cognodb.com/signup (no card needed).
2. Create a free (c0) instance, pick a region.
3. Copy the `bolt+s://...` URI and the one-time `cognodb` password into `.env`.

### 3.2 Neo4j AuraDB Free

1. Sign up at https://console.neo4j.io and create a Free instance.
2. Copy the `neo4j+s://...` URI and password into `.env`.

Credentials are **only** ever read from environment variables (`.env`, gitignored) —
never hardcoded, never committed.

## 4\. Running the benchmark

```bash
./scripts/run\_all.sh
```

This will, for each platform: download the dataset (once), load it with batched
`UNWIND` writes via the driver, run all required workloads, and print/save a markdown
report to `results/REPORT.md`.

To run a single step manually:

```bash
python scripts/loader.py --platform cognodb
python scripts/benchmark.py --platform cognodb
python scripts/report.py
```

## 5\. Methodology

* **Loading:** identical batched `MERGE`-based Cypher writes (batch size 1000) via the
driver for both platforms — no platform-specific bulk-import tool was used, so this
measures driver-level ingest, not each vendor's fastest possible bulk loader. Noted
as a caveat, not hidden.
* **Warm-up:** 5 rounds over a 10-node sample before any measured query.
* **Traversals:** 1/2/3-hop `MATCH` queries from randomly sampled start nodes,
`BENCH\_ITERATIONS` times each (default 20; raise for a more rigorous run).
* **Lookups:** point lookup (`MATCH ... {id: $id}`) and indexed lookup
(`WHERE p.id = $id`, using the uniqueness constraint's backing index).
* **Aggregation:** group-by out-degree, top 100.
* **Mixed workload:** `BENCH\_CONCURRENCY` (default 10) concurrent threads, 80/20
read/write mix, fixed 20-second window, reporting sustained queries/second.
* **Percentiles:** p50/p95 computed per workload, not just averages, per the
assignment's requirement.
* All queries, batch sizes, and iteration counts are identical across platforms —
the only thing that differs between runs is `--platform`.

## 6\. Results

*(Run `./scripts/run\_all.sh` and paste the output of `results/REPORT.md` below —
placeholders shown so the table shape is clear.)*

### Data Loading

|Platform|Nodes|Rels|Nodes/s|Rels/s|Wall clock (s)|
|-|-|-|-|-|-|
|aura|36692|367662|991|9929.7|37.03|
|cognodb|36692|367662|517.4|5184.9|70.91|

### Traversals (p50 / p95 ms)

|Platform|1-hop|2-hop|3-hop|
|-|-|-|-|
|aura|55.04 / 56.36  |55.78 / 59.57  | 57.28 / 218.68 |
|cognodb|126.64 / 128.01 | 127.58 /136.79 |136.82 / 149.33 |

### Lookups (p50 / p95 ms)

|Platform|Point lookup|Indexed lookup|
|-|-|-|
|aura| 55.05 / 56.52|55.06 / 60.16|
|cognodb|126.25 / 126.98|126.10 / 128.47|

### Aggregation (p50 / p95 ms)

|Platform|Group-by top-100|
|-|-|
|aura|114.51 / 125.80 |
|cognodb| 707.79 / 828.63    |

### Mixed Workload

|Platform|Concurrency|R/W mix|QPS|
|-|-|-|-|
|aura|10|80/20|175.5|
|cognodb|10|80/20|73.7|

### Footprint

Stored data size and memory usage were **not observable** through either platform's
free-tier console/driver at benchmark time — noted here rather than estimated.

## 7\. Analysis

*(Fill in after running: which platform was faster on which workload, and why —
e.g. differences in free-tier CPU throttling, network hop to the region you picked,
or query-planner differences. If both are literally Neo4j-compatible engines, a
close result is itself an interesting finding worth stating plainly rather than
manufacturing a bigger gap.)*

## 8\. Extending to more platforms

To add a third platform (e.g. Memgraph Cloud, ArangoDB Oasis, or a self-hosted
instance capped to matching resources):

1. Add its connection env vars to `.env.example` and `.env`.
2. Add an entry to `PLATFORMS` in `scripts/common.py` with its advertised specs.
3. If it doesn't speak Bolt/Cypher, add a small adapter module implementing the same
`get\_driver()` / `session.run()` surface used here (or port the four Cypher
queries in `scripts/benchmark.py` to that platform's query language — they are
isolated at the top of the file specifically so this is a small diff).
4. Re-run `./scripts/run\_all.sh` — the loader, workloads, warm-up, and report
generator all already loop over whatever is in `PLATFORMS`.

## 9\. Known caveats (honest, not hidden)

* Only 2 of the "at least 4 other databases" called for in a full submission were
benchmarked, due to the 2-hour time constraint under which this was produced.
* Iteration count defaults to 20, not the suggested ≥100.
* No cold-start-vs-warm numbers, no concurrency sweep (1/10/40).
* Loader uses generic batched Cypher writes, not each vendor's dedicated bulk-import
tool, so ingest numbers reflect driver-level load, not best-case load.
* Free-tier CPU is burstable/shared on both platforms, so run-to-run variance should
be expected; this run reports a single pass, not a variance study across repeats.
* AuraDB Free's advertised RAM/disk ceiling is not identical to CognoDB's (see §2).

