#!/usr/bin/env python3
"""
Shared metadata helpers for video date handling.

Used by both repair_video_dates.py (fixing already-converted files) and
process.py (the compression pipeline) so the two can never drift apart.

Why this exists: ffmpeg re-encoding drops QuickTime creation dates unless
they are explicitly re-written, and `exiftool -TagsFromFile -All:All` cannot
write most QuickTime groups. Photos.app reads QuickTime:CreateDate and
Keys:CreationDate (com.apple.quicktime.creationdate, timezone-aware), so
those must be written explicitly.
"""

import json
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone

# Tags Photos.app and Spotlight actually use, written explicitly because
# exiftool's QuickTime write support is per-group, not -All:All.
VIDEO_DATE_TAGS = [
    '-QuickTime:CreateDate',
    '-QuickTime:ModifyDate',
    '-TrackCreateDate',
    '-TrackModifyDate',
    '-MediaCreateDate',
    '-MediaModifyDate',
    '-Keys:CreationDate',
    '-Keys:GPSCoordinates',
    '-Keys:Make',
    '-Keys:Model',
    '-Keys:Software',
]

EXIFTOOL_DATE_RE = re.compile(
    r'^(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})(?:\.\d+)?'
    r'(?:([+-]\d{2}):(\d{2})|Z)?$'
)


def parse_exiftool_date(value):
    """Parse an exiftool date string to an aware datetime, or None.

    Accepts '2018:09:08 12:35:32', with optional fractional seconds and
    '+01:00'/'Z' offset. Naive values are treated as UTC (exiftool is run
    with -api QuickTimeUTC=1 so QuickTime dates come back in UTC).
    Rejects the null '0000:00:00 00:00:00'.
    """
    if not value:
        return None
    m = EXIFTOOL_DATE_RE.match(value.strip())
    if not m:
        return None
    year, month, day, hour, minute, second = (int(m.group(i)) for i in range(1, 7))
    if year == 0:
        return None
    if m.group(7) is not None:
        sign = 1 if m.group(7).startswith('+') else -1
        offset = timezone(sign * timedelta(
            hours=abs(int(m.group(7))), minutes=int(m.group(8))))
    else:
        offset = timezone.utc
    try:
        return datetime(year, month, day, hour, minute, second, tzinfo=offset)
    except ValueError:
        return None


def read_video_dates(path, timeout=60):
    """Read the date/GPS tags from a video via exiftool.

    Returns a dict of tag name -> raw string (only tags present), plus a
    parsed 'best_datetime' (Keys:CreationDate preferred, else CreateDate).
    Returns None if exiftool fails.
    """
    cmd = [
        'exiftool', '-api', 'QuickTimeUTC=1', '-j', '-G1',
        '-QuickTime:CreateDate', '-Keys:CreationDate',
        '-Keys:GPSCoordinates', '-Keys:Make', '-Keys:Model',
        path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    data = json.loads(result.stdout)[0]
    tags = {k: v for k, v in data.items() if k != 'SourceFile'}

    keys_date = parse_exiftool_date(str(data.get('Keys:CreationDate', '')))
    qt_date = parse_exiftool_date(str(data.get('QuickTime:CreateDate', '')))
    tags['best_datetime'] = keys_date or qt_date
    return tags


def copy_video_metadata(source_path, dest_path, keep_backup=True, timeout=120):
    """Copy date/GPS/device tags from source video to dest video in place.

    Metadata-only rewrite, no re-encode. With keep_backup, exiftool leaves
    '<dest>_original' next to the file for rollback.
    Returns (success, error_message).
    """
    cmd = ['exiftool', '-api', 'QuickTimeUTC=1', '-TagsFromFile', source_path]
    cmd.extend(VIDEO_DATE_TAGS)
    if not keep_backup:
        cmd.append('-overwrite_original')
    cmd.append(dest_path)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, 'exiftool timeout'
    if result.returncode != 0:
        return False, (result.stderr or result.stdout)[:300]
    return True, None


def set_file_times(path, dt):
    """Set the file's atime/mtime to the given aware datetime."""
    epoch = dt.timestamp()
    os.utime(path, (epoch, epoch))


def ffprobe_duration(path, timeout=60):
    """Return the container duration in seconds, or None."""
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    if result.returncode != 0:
        return None
    try:
        return float(json.loads(result.stdout)['format']['duration'])
    except (KeyError, ValueError, json.JSONDecodeError):
        return None
