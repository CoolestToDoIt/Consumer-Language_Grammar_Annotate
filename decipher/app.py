"""Small entry point for the local commercial workspace."""
import argparse
from pathlib import Path
from .gloss_web import serve


def main():
    parser = argparse.ArgumentParser(description='Decipher Lab local annotation workspace (single operator).')
    parser.add_argument('--workspace-dir', type=Path, default=Path.home() / '.decipher' / 'projects', help='Directory containing local .dproj files')
    parser.add_argument('--port', type=int, default=8765, help='Loopback HTTP port (default: 8765)')
    parser.add_argument('--version', action='version', version='Decipher Lab Pilot 0.1.0')
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error('--port must be between 0 and 65535')
    args.workspace_dir.expanduser().mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        serve(args.workspace_dir, args.port)
    except KeyboardInterrupt:
        print('\nWorkspace stopped. Saved projects remain on disk.')


if __name__ == '__main__':
    main()
