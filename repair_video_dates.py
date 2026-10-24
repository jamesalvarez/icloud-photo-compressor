#!/usr/bin/env python3
"""
Repair creation dates on converted videos that lost their metadata.

The November 2025 compression run re-encoded videos without copying
QuickTime creation dates, leaving CreateDate 0000:00:00 on every MP4.
This script joins each converted video back to its original by filename
stem, copies the date/GPS/device tags across (metadata-only, no
re-encode), verifies the result, and sets file times to the capture date.

Safe by design:
- originals are opened read-only, never written
- exiftool keeps a '<file>_original' backup beside each repaired file;
  verification failure auto-restores it
- resumable via a state file; --dry-run and --limit for pilots

Usage:
  python3 repair_video_dates.py \
    --originals "/path/to/Originals" \
    --converted "/path/to/Converted" \
    --state ~/.photo-fix/repair_state.json \
    [--dry-run] [--limit N]
"""

import argparse
import csv
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

from metadata_utils import (
    copy_video_metadata,
    ffprobe_duration,
    read_video_dates,
    set_file_times,
)

VIDEO_SOURCE_EXTS = {'.mov', '.mp4', '.m4v', '.avi', '.3gp'}


def build_original_index(originals_dir):
    """Map lowercase stem -> list of original video Paths."""
    index = {}
    for p in Path(originals_dir).iterdir():
        if p.suffix.lower() in VIDEO_SOURCE_EXTS:
            index.setdefault(p.stem.lower(), []).append(p)
    return index


def load_state(state_path):
    if state_path.exists():
        with open(state_path) as f:
            return json.load(f)
    return {'repaired': {}, 'failed': {}, 'skipped': {}}


def save_state(state, state_path):
    state['last_updated'] = datetime.now().isoformat()
    with open(state_path, 'w') as f:
        json.dump(state, f, indent=2)


def write_csv(path, rows, header):
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--originals', required=True)
    parser.add_argument('--converted', required=True)
    parser.add_argument('--state', required=True)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()

    originals_dir = Path(args.originals).expanduser()
    converted_dir = Path(args.converted).expanduser()
    state_path = Path(args.state).expanduser()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    report_dir = state_path.parent

    index = build_original_index(originals_dir)
    converted = sorted(converted_dir.glob('*.mp4'))
    state = load_state(state_path)

    ambiguous, no_source_date, failures = [], [], []
    done = 0

    print(f"{len(converted)} converted mp4s, {len(index)} original video stems")

    for conv in converted:
        key = str(conv)
        if key in state['repaired']:
            continue
        if args.limit and done >= args.limit:
            break

        matches = index.get(conv.stem.lower(), [])
        if len(matches) != 1:
            reason = 'no original found' if not matches else \
                f"{len(matches)} candidate originals: {[m.name for m in matches]}"
            ambiguous.append((conv.name, reason))
            state['skipped'][key] = reason
            continue
        orig = matches[0]

        src_tags = read_video_dates(orig)
        if not src_tags or not src_tags.get('best_datetime'):
            no_source_date.append((conv.name, orig.name))
            state['skipped'][key] = 'original has no usable date'
            continue

        if args.dry_run:
            print(f"[dry-run] {conv.name} <- {orig.name} "
                  f"({src_tags['best_datetime'].isoformat()})")
            done += 1
            continue

        duration_before = ffprobe_duration(conv)

        ok, err = copy_video_metadata(str(orig), str(conv), keep_backup=True)
        backup = conv.with_name(conv.name + '_original')

        if ok:
            dst_tags = read_video_dates(conv)
            duration_after = ffprobe_duration(conv)
            problems = []
            if not dst_tags or not dst_tags.get('best_datetime'):
                problems.append('date missing after write')
            elif dst_tags['best_datetime'] != src_tags['best_datetime']:
                problems.append(
                    f"date mismatch {dst_tags['best_datetime']} != "
                    f"{src_tags['best_datetime']}")
            if duration_before and duration_after:
                if abs(duration_before - duration_after) > 0.1:
                    problems.append('duration changed')
            elif duration_before and not duration_after:
                problems.append('ffprobe failed after write')
            if problems:
                ok, err = False, '; '.join(problems)

        if not ok:
            if backup.exists():
                shutil.move(str(backup), str(conv))
            failures.append((conv.name, err))
            state['failed'][key] = err
            print(f"FAILED {conv.name}: {err}", file=sys.stderr)
            continue

        set_file_times(conv, src_tags['best_datetime'])
        state['repaired'][key] = {
            'original': str(orig),
            'date': src_tags['best_datetime'].isoformat(),
            'repaired_at': datetime.now().isoformat(),
        }
        done += 1
        if done % 25 == 0:
            save_state(state, state_path)
            print(f"progress: {done} repaired this run, "
                  f"{len(state['repaired'])} total")

    save_state(state, state_path)
    write_csv(report_dir / 'ambiguous.csv', ambiguous, ['converted', 'reason'])
    write_csv(report_dir / 'no_source_date.csv', no_source_date,
              ['converted', 'original'])
    write_csv(report_dir / 'repair_failures.csv', failures,
              ['converted', 'error'])

    print(f"\nrepaired (total): {len(state['repaired'])}")
    print(f"ambiguous joins:  {len(ambiguous)}")
    print(f"no source date:   {len(no_source_date)}")
    print(f"failures:         {len(failures)}")


if __name__ == '__main__':
    main()
