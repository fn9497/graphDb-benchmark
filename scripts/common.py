import os
import time
import statistics
from contextlib import contextmanager
from dotenv import load_dotenv
from neo4j import GraphDatabase, TrustAll

load_dotenv()

TRUST_ANY_CERT = os.getenv("TRUST_ANY_CERT", "true").lower() == "true"
load_dotenv()

PLATFORMS = {
    "cognodb": {
        "uri": os.getenv("COGNODB_URI"),
        "user": os.getenv("COGNODB_USER", "cognodb"),
        "password": os.getenv("COGNODB_PASSWORD"),
        "advertised_specs": "Free tier (c0): burstable 0.5 vCPU, 256 MB RAM, 1 GB disk",
    },
    "aura": {
        "uri": os.getenv("AURA_URI"),
        "user": os.getenv("AURA_USER", "neo4j"),
        "password": os.getenv("AURA_PASSWORD"),
        "advertised_specs": "AuraDB Free: shared vCPU, 1 GB RAM, 8 GB disk cap "
        "(entry-level free tier; document actual observed limits in README)",
    },
}


def get_driver(platform_key: str):
    cfg = PLATFORMS[platform_key]
    if not cfg["uri"] or not cfg["password"]:
        raise RuntimeError(
            f"Missing credentials for '{platform_key}'. Fill them in .env (see .env.example)."
        )
    return GraphDatabase.driver(cfg["uri"], auth=(cfg["user"], cfg["password"]))
@contextmanager
def timed():
    start = time.perf_counter()
    yield lambda: (time.perf_counter() - start) * 1000  # ms


def percentiles(latencies_ms, ps=(50, 95)):
    if not latencies_ms:
        return {p: None for p in ps}
    s = sorted(latencies_ms)
    out = {}
    for p in ps:
        k = (len(s) - 1) * (p / 100)
        f = int(k)
        c = min(f + 1, len(s) - 1)
        out[p] = s[f] + (s[c] - s[f]) * (k - f)
    return out


def run_timed_query(session, cypher, params=None, n=1):
    """Run a query n times (after this call is itself expected to be post-warmup),
    return list of latencies in ms."""
    latencies = []
    for _ in range(n):
        with timed() as t:
            session.run(cypher, params or {}).consume()
        latencies.append(t())
    return latencies
