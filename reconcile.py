#!/usr/bin/env python3
"""
Reconcile source media against converted output.

For every source file, determine whether it has a converted counterpart
(by filename stem) and, if not, why: failed or skipped per the original
run's progress file, or silently absent. Writes missing_media.csv and
prints a summary. Read-only.

Usage:
  python3 reconcile.py --originals <dir> --converted <dir> \
    --progress <process_progress.json> --out missing_media.csv
"""

import argparse
import csv
import json
from pathlib import Path

IMAGE_EXTS = {'.heic', '.jpg', '.jpeg', '.png', '.gif', '.tiff', '.bmp'}
VIDEO_EXTS = {'.mov', '.mp4', '.m4v', '.avi', '.3gp'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--originals', required=True)
    parser.add_argument('--converted', required=True)
    parser.add_argument('--progress', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()

    # Match within media type: Live Photos pair a HEIC and a MOV on the
    # same stem, so a stem-only match would hide missing videos.
    converted_image_stems = set()
    converted_video_stems = set()
    for p in Path(args.converted).iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() in VIDEO_EXTS:
            converted_video_stems.add(p.stem.lower())
        elif p.suffix.lower() in IMAGE_EXTS:
            converted_image_stems.add(p.stem.lower())

    with open(Path(args.progress).expanduser()) as f:
        progress = json.load(f)
    # Progress keys are full paths from the original run; index by filename.
    failed = {Path(k).name: v for k, v in progress.get('failed_files', {}).items()}
    skipped = {Path(k).name: v for k, v in progress.get('skipped_files', {}).items()}

    rows = []
    counts = {'converted': 0, 'failed': 0, 'skipped': 0, 'absent': 0,
              'sidecar': 0}

    for p in sorted(Path(args.originals).iterdir()):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext not in IMAGE_EXTS and ext not in VIDEO_EXTS:
            counts['sidecar'] += 1
            continue
        media = 'video' if ext in VIDEO_EXTS else 'image'
        matched = (converted_video_stems if media == 'video'
                   else converted_image_stems)
        if p.stem.lower() in matched:
            counts['converted'] += 1
            continue
        if p.name in failed:
            status, detail = 'failed', failed[p.name]
        elif p.name in skipped:
            status, detail = 'skipped', str(skipped[p.name])
        else:
            status, detail = 'absent', 'no converted output and no log entry'
        counts[status] += 1
        rows.append((p.name, media, status, detail[:200]))

    with open(Path(args.out).expanduser(), 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['source', 'media_type', 'status', 'detail'])
        writer.writerows(rows)

    total = sum(counts.values())
    print(f"sources examined: {total}")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    print(f"unconverted rows written to {args.out}: {len(rows)}")


if __name__ == '__main__':
    main()
