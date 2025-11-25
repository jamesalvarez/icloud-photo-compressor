#!/usr/bin/env python3
"""
Media Analyzer - Scans and catalogs all photos and videos
Extracts metadata including resolution, file size, codec, etc.
"""

import os
import csv
import json
import subprocess
from pathlib import Path
from datetime import datetime
from PIL import Image
import pillow_heif

# Register HEIF opener with Pillow
pillow_heif.register_heif_opener()

# Configuration
ORIGINALS_DIR = "Originals"
OUTPUT_CSV = "media_catalog.csv"
PROGRESS_FILE = "analyze_progress.json"

# Supported formats
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.heic', '.gif', '.bmp', '.tiff'}
VIDEO_EXTENSIONS = {'.mov', '.mp4', '.avi', '.mkv', '.m4v', '.hevc'}


def load_progress():
    """Load progress from previous run"""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {'processed_files': [], 'last_updated': None}


def save_progress(progress):
    """Save progress for resume capability"""
    progress['last_updated'] = datetime.now().isoformat()
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)


def get_image_info(filepath):
    """Extract metadata from image files"""
    try:
        with Image.open(filepath) as img:
            width, height = img.size
            format_name = img.format
            mode = img.mode

            # Get file size
            file_size = os.path.getsize(filepath)

            return {
                'filepath': filepath,
                'filename': os.path.basename(filepath),
                'media_type': 'image',
                'file_type': format_name or os.path.splitext(filepath)[1][1:].upper(),
                'width': width,
                'height': height,
                'resolution': f"{width}x{height}",
                'file_size_bytes': file_size,
                'file_size_mb': round(file_size / (1024 * 1024), 2),
                'color_mode': mode,
                'codec': 'N/A',
                'bitrate': 'N/A',
                'duration': 'N/A',
                'fps': 'N/A',
                'error': None
            }
    except Exception as e:
        return {
            'filepath': filepath,
            'filename': os.path.basename(filepath),
            'media_type': 'image',
            'error': str(e)
        }


def get_video_info(filepath):
    """Extract metadata from video files using ffprobe"""
    try:
        # Use ffprobe to get video information
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            filepath
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise Exception("ffprobe failed")

        data = json.loads(result.stdout)

        # Find video stream
        video_stream = None
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                video_stream = stream
                break

        if not video_stream:
            raise Exception("No video stream found")

        width = video_stream.get('width', 0)
        height = video_stream.get('height', 0)
        codec = video_stream.get('codec_name', 'unknown')

        # Get format info
        format_info = data.get('format', {})
        file_size = int(format_info.get('size', 0))
        duration = float(format_info.get('duration', 0))
        bitrate = int(format_info.get('bit_rate', 0))

        # Calculate FPS
        fps = 'N/A'
        if 'r_frame_rate' in video_stream:
            try:
                num, den = map(int, video_stream['r_frame_rate'].split('/'))
                fps = round(num / den, 2)
            except:
                pass

        return {
            'filepath': filepath,
            'filename': os.path.basename(filepath),
            'media_type': 'video',
            'file_type': os.path.splitext(filepath)[1][1:].upper(),
            'width': width,
            'height': height,
            'resolution': f"{width}x{height}",
            'file_size_bytes': file_size,
            'file_size_mb': round(file_size / (1024 * 1024), 2),
            'color_mode': 'N/A',
            'codec': codec,
            'bitrate': bitrate,
            'bitrate_mbps': round(bitrate / 1000000, 2) if bitrate > 0 else 'N/A',
            'duration': round(duration, 2),
            'fps': fps,
            'error': None
        }
    except Exception as e:
        return {
            'filepath': filepath,
            'filename': os.path.basename(filepath),
            'media_type': 'video',
            'error': str(e)
        }


def scan_media_files():
    """Scan all media files in Originals directory"""
    media_files = []

    originals_path = Path(ORIGINALS_DIR)
    if not originals_path.exists():
        print(f"Error: {ORIGINALS_DIR} directory not found!")
        return []

    print(f"Scanning {ORIGINALS_DIR} directory...")

    for root, dirs, files in os.walk(originals_path):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in IMAGE_EXTENSIONS or ext in VIDEO_EXTENSIONS:
                filepath = os.path.join(root, file)
                media_files.append(filepath)

    return media_files


def analyze_media(resume=True):
    """Main analysis function"""
    print("=" * 70)
    print("MEDIA ANALYZER")
    print("=" * 70)

    # Load progress if resuming
    progress = load_progress() if resume else {'processed_files': []}
    processed_set = set(progress.get('processed_files', []))

    # Scan for media files
    media_files = scan_media_files()
    total_files = len(media_files)

    if total_files == 0:
        print("No media files found!")
        return

    print(f"Found {total_files} media files")

    # Filter out already processed files
    if resume and processed_set:
        remaining_files = [f for f in media_files if f not in processed_set]
        print(f"Resuming from previous run: {len(remaining_files)} files remaining")
        media_files = remaining_files

    # Determine if we're appending or creating new
    write_mode = 'a' if resume and os.path.exists(OUTPUT_CSV) else 'w'
    write_header = write_mode == 'w'

    # Process files
    fieldnames = [
        'filepath', 'filename', 'media_type', 'file_type', 'width', 'height',
        'resolution', 'file_size_bytes', 'file_size_mb', 'color_mode',
        'codec', 'bitrate', 'bitrate_mbps', 'duration', 'fps', 'error'
    ]

    with open(OUTPUT_CSV, write_mode, newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')

        if write_header:
            writer.writeheader()

        for idx, filepath in enumerate(media_files, 1):
            print(f"\n[{idx}/{len(media_files)}] Processing: {os.path.basename(filepath)}")

            ext = os.path.splitext(filepath)[1].lower()

            if ext in IMAGE_EXTENSIONS:
                info = get_image_info(filepath)
            elif ext in VIDEO_EXTENSIONS:
                info = get_video_info(filepath)
            else:
                continue

            if info.get('error'):
                print(f"  ERROR: {info['error']}")
            else:
                print(f"  Type: {info['media_type']}")
                print(f"  Resolution: {info['resolution']}")
                print(f"  Size: {info['file_size_mb']} MB")
                if info['media_type'] == 'video':
                    print(f"  Codec: {info['codec']}")
                    print(f"  Duration: {info['duration']}s")

            writer.writerow(info)

            # Update progress
            processed_set.add(filepath)
            if idx % 10 == 0:  # Save progress every 10 files
                progress['processed_files'] = list(processed_set)
                save_progress(progress)

    # Final progress save
    progress['processed_files'] = list(processed_set)
    save_progress(progress)

    print("\n" + "=" * 70)
    print(f"Analysis complete! Results saved to {OUTPUT_CSV}")
    print(f"Total files processed: {len(processed_set)}")
    print("=" * 70)

    # Generate summary
    print_summary()


def print_summary():
    """Print summary statistics from the catalog"""
    if not os.path.exists(OUTPUT_CSV):
        return

    with open(OUTPUT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    images = [r for r in rows if r['media_type'] == 'image']
    videos = [r for r in rows if r['media_type'] == 'video']
    errors = [r for r in rows if r.get('error')]

    total_size_mb = sum(float(r['file_size_mb']) for r in rows if r.get('file_size_mb') and r.get('error') is None)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total files: {len(rows)}")
    print(f"Images: {len(images)}")
    print(f"Videos: {len(videos)}")
    print(f"Errors: {len(errors)}")
    print(f"Total size: {total_size_mb / 1024:.2f} GB")

    # Resolution distribution
    if rows:
        resolutions = {}
        for row in rows:
            if row.get('resolution') and not row.get('error'):
                res = row['resolution']
                resolutions[res] = resolutions.get(res, 0) + 1

        print(f"\nTop 10 resolutions:")
        for res, count in sorted(resolutions.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {res}: {count} files")

    print("=" * 70)


if __name__ == "__main__":
    import sys

    # Check for ffprobe
    try:
        subprocess.run(['ffprobe', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: ffprobe not found. Please install ffmpeg:")
        print("  macOS: brew install ffmpeg")
        print("  Linux: sudo apt-get install ffmpeg")
        sys.exit(1)

    # Check for arguments
    resume = True
    if '--no-resume' in sys.argv:
        resume = False
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)
        print("Starting fresh analysis (ignoring previous progress)")

    try:
        analyze_media(resume=resume)
    except KeyboardInterrupt:
        print("\n\nInterrupted! Progress has been saved.")
        print("Run the script again to resume from where you left off.")
        sys.exit(0)
