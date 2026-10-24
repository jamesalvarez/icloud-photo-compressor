#!/usr/bin/env python3
"""
Consolidate an icloudpd staging download into the Originals archive.

iCloud holds a mixture: compressed re-uploads of the old corpus (our own
Converted files) and true new originals. This script classifies every
staged file and copies ONLY true new originals into the Originals
directory. It never moves or deletes; staging stays intact for the
caller to remove after verification.

Classification per staged file:
  - stem already present in the Originals manifest -> skip (already archived,
    or a compressed re-upload of an archived item)
  - novel-stem MP4 whose encoder tag is Lavf* -> skip + flag (one of our own
    compressed files; should not have a novel stem — investigate)
  - otherwise -> new original: copy into Originals (collision with different
    size gets a ' (new-N)' suffix and a flag)

Usage:
  python3 consolidate.py --staging <dir> --originals <dir> \
    --report <report.csv> [--execute]   (default is dry-run)
"""

import argparse
import csv
import json
import shutil
import subprocess
from pathlib import Path

MEDIA_EXTS = {'.heic', '.jpg', '.jpeg', '.png', '.gif', '.tiff', '.bmp',
              '.mov', '.mp4', '.m4v', '.avi', '.3gp', '.aae', '.dng'}


def encoder_tag(path):
    """Return the container encoder tag (e.g. 'Lavf61.7.100'), or ''."""
    cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json',
           '-show_format', str(path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=60)
        return json.loads(result.stdout)['format']['tags'].get('encoder', '')
    except Exception:
        return ''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--staging', required=True)
    parser.add_argument('--originals', required=True)
    parser.add_argument('--report', required=True)
    parser.add_argument('--execute', action='store_true',
                        help='actually copy; default is dry-run')
    args = parser.parse_args()

    staging = Path(args.staging).expanduser()
    originals = Path(args.originals).expanduser()

    existing_stems = {p.stem.lower() for p in originals.iterdir()
                      if p.is_file()}

    rows = []
    counts = {'already_archived': 0, 'compressed_reupload': 0,
              'new_original': 0, 'collision': 0, 'non_media': 0}

    staged = sorted(p for p in staging.rglob('*') if p.is_file())
    print(f"{len(staged)} staged files, {len(existing_stems)} existing stems"
          f"{' (EXECUTE)' if args.execute else ' (dry-run)'}")

    for p in staged:
        if p.suffix.lower() not in MEDIA_EXTS:
            counts['non_media'] += 1
            rows.append((p.name, 'non_media', ''))
            continue
        if p.stem.lower() in existing_stems:
            counts['already_archived'] += 1
            rows.append((p.name, 'already_archived', ''))
            continue
        if p.suffix.lower() == '.mp4':
            enc = encoder_tag(p)
            if enc.startswith('Lavf'):
                counts['compressed_reupload'] += 1
                rows.append((p.name, 'compressed_reupload_FLAG', enc))
                continue

        dest = originals / p.name
        note = ''
        if dest.exists():
            if dest.stat().st_size == p.stat().st_size:
                counts['already_archived'] += 1
                rows.append((p.name, 'already_archived', 'same name+size'))
                continue
            n = 1
            while dest.exists():
                dest = originals / f"{p.stem} (new-{n}){p.suffix}"
                n += 1
            counts['collision'] += 1
            note = f'renamed to {dest.name}'
            rows.append((p.name, 'collision_FLAG', note))
        else:
            rows.append((p.name, 'new_original', ''))
        counts['new_original'] += 1

        if args.execute:
            shutil.copy2(p, dest)
            existing_stems.add(dest.stem.lower())

    with open(Path(args.report).expanduser(), 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['staged_file', 'classification', 'note'])
        writer.writerows(rows)

    for k, v in counts.items():
        print(f"  {k}: {v}")
    if not args.execute:
        print("dry-run only — re-run with --execute to copy new originals")


if __name__ == '__main__':
    main()
