"""
Downloads the SNAP email-Enron dataset (directed communication network).

Source: https://snap.stanford.edu/data/email-Enron.html
~36,692 nodes, ~183,831 edges (directed) -> fits the 100k-500k relationship
range required by the assignment, and is small enough to fit every free tier.

Usage:
    python scripts/download_dataset.py
"""
import gzip
import os
import shutil
import requests

URL = "https://snap.stanford.edu/data/email-Enron.txt.gz"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
GZ_PATH = os.path.join(OUT_DIR, "email-Enron.txt.gz")
TXT_PATH = os.path.join(OUT_DIR, "email-Enron.txt")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    if os.path.exists(TXT_PATH):
        print(f"Dataset already present at {TXT_PATH}")
        return

    print(f"Downloading {URL} ...")
    r = requests.get(URL, stream=True, timeout=60)
    r.raise_for_status()
    with open(GZ_PATH, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)

    print("Decompressing ...")
    with gzip.open(GZ_PATH, "rb") as f_in, open(TXT_PATH, "w") as f_out:
        for line in f_in:
            line = line.decode("utf-8")
            if line.startswith("#"):
                continue
            f_out.write(line)

    os.remove(GZ_PATH)

    with open(TXT_PATH) as f:
        n_edges = sum(1 for _ in f)
    print(f"Done. {TXT_PATH} has {n_edges} edges.")


if __name__ == "__main__":
    main()
