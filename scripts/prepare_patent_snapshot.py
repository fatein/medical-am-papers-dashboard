"""Build the credential-free patent snapshot from the final strict JSONL export."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dashboard.patent_data import build_snapshot

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', default=ROOT, type=Path)
    parser.add_argument('--expected-count', default=5516, type=int)
    args = parser.parse_args()
    print(json.dumps(build_snapshot(args.source, args.output, args.expected_count), indent=2))
