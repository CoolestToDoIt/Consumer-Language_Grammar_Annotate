"""Explicitly fetch checksum-pinned corpus files, or verify an offline cache."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    sources = json.loads((ROOT/'data/corpora/SOURCES.json').read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', choices=tuple(sources), action='append')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    for name in args.corpus or sources:
        entry = sources[name]
        directory = ROOT/'data/corpora'/name
        directory.mkdir(parents=True, exist_ok=True)
        print(f"{name}: {entry['release']}; {entry['license']}")
        for filename, metadata in entry['files'].items():
            destination = directory/filename
            if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() == metadata['sha256']:
                continue
            if args.verify_only:
                raise SystemExit(f'Missing or checksum mismatch: {destination}')
            # No credentials are used; only the explicit public URLs in SOURCES.json.
            with urllib.request.urlopen(metadata['url'], timeout=60) as response:
                content = response.read()
            if hashlib.sha256(content).hexdigest() != metadata['sha256']:
                raise SystemExit(f'Upstream checksum mismatch: {metadata["url"]}')
            with tempfile.NamedTemporaryFile(dir=directory, delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(content)
            try:
                temporary.replace(destination)
            finally:
                temporary.unlink(missing_ok=True)
        print('  All file checksums verified.')

if __name__ == '__main__':
    main()
