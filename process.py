#!/usr/bin/env python3
"""
Media Processor - Batch processes media files according to compression strategies
Supports resume capability, validation, and detailed logging
"""

import os
import csv
import yaml
import json
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from PIL import Image
import pillow_heif

from metadata_utils import (
    copy_video_metadata,
    read_video_dates,
    set_file_times,
)

# Register HEIF opener with Pillow
pillow_heif.register_heif_opener()

# Configuration
INPUT_CSV = "media_catalog.csv"
CONFIG_FILE = "compression_config.yaml"
PROGRESS_FILE = "process_progress.json"
LOG_FILE = "process_log.txt"


class Logger:
    """Simple logger for both file and console output"""

    def __init__(self, log_file):
        self.log_file = log_file
        self.log_handle = open(log_file, 'a', encoding='utf-8')

    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{level}] {message}"
        print(log_message)
        self.log_handle.write(log_message + "\n")
        self.log_handle.flush()

    def close(self):
        self.log_handle.close()


def load_config():
    """Load compression configuration"""
    if not Path(CONFIG_FILE).exists():
        raise FileNotFoundError(f"{CONFIG_FILE} not found. Run generate_config.py first.")

    with open(CONFIG_FILE, 'r') as f:
        return yaml.safe_load(f)


def load_catalog():
    """Load media catalog"""
    if not Path(INPUT_CSV).exists():
        raise FileNotFoundError(f"{INPUT_CSV} not found. Run analyze.py first.")

    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return [row for row in reader if not row.get('error')]


def load_progress():
    """Load processing progress"""
    if Path(PROGRESS_FILE).exists():
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {
        'processed_files': {},
        'failed_files': {},
        'skipped_files': {},
        'stats': {
            'total_original_size_mb': 0,
            'total_converted_size_mb': 0,
            'files_processed': 0,
            'files_failed': 0,
            'files_skipped': 0
        }
    }


def save_progress(progress):
    """Save processing progress"""
    progress['last_updated'] = datetime.now().isoformat()
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)


def parse_resolution(resolution_str):
    """Parse resolution string into width and height"""
    if not resolution_str or resolution_str == 'N/A':
        return 0, 0
    try:
        width, height = map(int, resolution_str.split('x'))
        return width, height
    except:
        return 0, 0


def get_resolution_category(width, height):
    """Categorize resolution into standard groups"""
    pixels = width * height

    if pixels == 0:
        return "unknown"
    elif pixels <= 640 * 480:
        return "sd_480p"
    elif pixels <= 960 * 720:
        return "hd_720p"
    elif pixels <= 1920 * 1080:
        return "fhd_1080p"
    elif pixels <= 2560 * 1440:
        return "qhd_1440p"
    elif pixels <= 3840 * 2160:
        return "uhd_4k"
    else:
        return "uhd_8k_plus"


def match_strategy(file_data, config):
    """Match a file to its compression strategy"""
    media_type = file_data['media_type']

    if media_type == 'image':
        strategies = config.get('image_strategies', {})
    elif media_type == 'video':
        strategies = config.get('video_strategies', {})
    else:
        return None, None

    width, height = parse_resolution(file_data.get('resolution'))
    res_category = get_resolution_category(width, height)
    file_type = file_data.get('file_type')
    exact_res = file_data.get('resolution')

    # Try to find matching strategy
    for strategy_name, strategy_config in strategies.items():
        matches = strategy_config.get('matches', {})

        # Match by exact resolution first
        if matches.get('exact_resolution') == exact_res and matches.get('file_type') == file_type:
            if media_type == 'video':
                if matches.get('codec') == file_data.get('codec'):
                    return strategy_name, strategy_config.get('strategy')
            else:
                return strategy_name, strategy_config.get('strategy')

    return None, None


def process_image(input_path, output_path, strategy, logger):
    """Process an image file"""
    try:
        with Image.open(input_path) as img:
            # Convert RGBA to RGB if saving as JPEG
            if img.mode in ('RGBA', 'LA', 'P') and strategy['output_format'].lower() == 'jpeg':
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = rgb_img

            # Resize if needed
            if strategy.get('max_dimension'):
                max_dim = strategy['max_dimension']
                if max(img.size) > max_dim:
                    img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                    logger.log(f"  Resized to {img.size[0]}x{img.size[1]}")

            # Save with specified quality
            save_params = {'quality': strategy.get('quality', 85), 'optimize': True}

            if strategy['output_format'].lower() == 'jpeg':
                save_params['progressive'] = True

            img.save(output_path, format=strategy['output_format'], **save_params)

        # Copy EXIF/GPS metadata from original using exiftool.
        # Explicit groups: -All:All silently fails to write many of them.
        try:
            cmd = [
                'exiftool',
                '-TagsFromFile', input_path,
                '-EXIF:all', '-GPS:all', '-ICC_Profile',
                '-overwrite_original',
                output_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                logger.log(f"  EXIF metadata copied")
            else:
                logger.log(f"  Warning: EXIF copy had issues: {result.stderr[:100]}", "WARN")
        except subprocess.TimeoutExpired:
            logger.log(f"  Warning: EXIF copy timeout", "WARN")
        except Exception as e:
            logger.log(f"  Warning: EXIF copy failed: {str(e)[:100]}", "WARN")

        # File times = capture date, so date-sorting works even where
        # a consumer ignores EXIF.
        try:
            cmd = ['exiftool', '-api', 'QuickTimeUTC=1', '-j',
                   '-DateTimeOriginal', '-OffsetTimeOriginal', input_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                import json as _json
                from metadata_utils import parse_exiftool_date
                data = _json.loads(result.stdout)[0]
                raw = str(data.get('DateTimeOriginal', ''))
                offset = str(data.get('OffsetTimeOriginal', ''))
                capture = parse_exiftool_date(
                    raw + offset if offset.startswith(('+', '-')) else raw)
                if capture:
                    set_file_times(output_path, capture)
        except Exception as e:
            logger.log(f"  Warning: could not set file times: {str(e)[:100]}", "WARN")

        return True, None

    except Exception as e:
        return False, str(e)


def process_video(input_path, output_path, strategy, logger):
    """Process a video file, preserving creation dates and GPS.

    ffmpeg drops QuickTime creation dates on re-encode unless passed
    explicitly, and the MP4 muxer only honours a plain
    '-metadata creation_time'. The exiftool pass afterwards writes the
    Keys/Track/Media variants that Photos.app reads.
    """
    try:
        # Read the source's capture date first; refuse to silently
        # produce an undated file if the source has a date.
        src_tags = read_video_dates(input_path)
        capture = src_tags.get('best_datetime') if src_tags else None
        if not capture:
            logger.log(f"  Warning: source has no creation date", "WARN")

        cmd = ['ffmpeg', '-i', input_path, '-y']

        # Copy all metadata streams
        cmd.extend(['-map_metadata', '0'])

        if capture:
            from datetime import timezone as _tz
            iso_utc = capture.astimezone(_tz.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            cmd.extend(['-metadata', f'creation_time={iso_utc}'])

        # Video codec
        video_codec = strategy.get('video_codec', 'libx264')
        cmd.extend(['-c:v', video_codec])

        # Apple software (Photos, QuickTime) rejects HEVC in mp4 unless the
        # sample entry is tagged hvc1 (ffmpeg defaults to hev1).
        if video_codec in ('libx265', 'hevc_videotoolbox'):
            cmd.extend(['-tag:v', 'hvc1'])

        # CRF (quality)
        cmd.extend(['-crf', str(strategy.get('crf', 23))])

        # Preset
        cmd.extend(['-preset', strategy.get('preset', 'medium')])

        # Resolution
        if strategy.get('max_resolution'):
            cmd.extend(['-vf', f"scale={strategy['max_resolution']}:force_original_aspect_ratio=decrease"])

        # Audio codec
        cmd.extend(['-c:a', strategy.get('audio_codec', 'aac')])
        cmd.extend(['-b:a', '128k'])

        cmd.extend(['-movflags', '+faststart'])

        # Output
        cmd.append(output_path)

        logger.log(f"  Running ffmpeg with metadata preservation")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout per video
        )

        if result.returncode != 0:
            return False, f"ffmpeg error: {result.stderr[-500:]}"  # Last 500 chars of error

        # Write the QuickTime/Keys date, GPS and device tags explicitly.
        ok, err = copy_video_metadata(input_path, output_path,
                                      keep_backup=False)
        if ok:
            logger.log(f"  Video dates/GPS copied with exiftool")
        else:
            logger.log(f"  Warning: exiftool metadata copy failed: {err}", "WARN")

        # Verify the output actually carries a date before declaring success.
        if capture:
            dst_tags = read_video_dates(output_path)
            if not dst_tags or dst_tags.get('best_datetime') != capture:
                return False, "creation date missing or wrong on output"
            set_file_times(output_path, capture)

        return True, None

    except subprocess.TimeoutExpired:
        return False, "Processing timeout (5 minutes)"
    except Exception as e:
        return False, str(e)


def validate_output(output_path, original_size_mb, skip_if_larger, logger):
    """Validate that output file is good"""
    if not Path(output_path).exists():
        return False, "Output file not created"

    output_size = os.path.getsize(output_path)
    output_size_mb = output_size / (1024 * 1024)

    logger.log(f"  Original: {original_size_mb:.2f} MB -> Converted: {output_size_mb:.2f} MB")

    if output_size == 0:
        return False, "Output file is empty"

    # Check if output is larger than original
    if skip_if_larger and output_size_mb > original_size_mb:
        logger.log(f"  WARNING: Converted file is larger, keeping original", "WARN")
        os.remove(output_path)
        return False, "Converted file is larger than original"

    reduction = ((original_size_mb - output_size_mb) / original_size_mb) * 100
    logger.log(f"  Size reduction: {reduction:.1f}%")

    return True, output_size_mb


def process_files(dry_run=False, resume=True):
    """Main processing function"""
    logger = Logger(LOG_FILE)

    logger.log("=" * 70)
    logger.log("MEDIA PROCESSOR" + (" - DRY RUN" if dry_run else ""))
    logger.log("=" * 70)

    # Load configuration
    try:
        config = load_config()
        logger.log(f"Loaded configuration from {CONFIG_FILE}")
    except Exception as e:
        logger.log(f"Error loading config: {e}", "ERROR")
        return

    # Load catalog
    try:
        catalog = load_catalog()
        logger.log(f"Loaded {len(catalog)} files from catalog")
    except Exception as e:
        logger.log(f"Error loading catalog: {e}", "ERROR")
        return

    # Load progress
    progress = load_progress() if resume else {
        'processed_files': {},
        'failed_files': {},
        'skipped_files': {},
        'stats': {
            'total_original_size_mb': 0,
            'total_converted_size_mb': 0,
            'files_processed': 0,
            'files_failed': 0,
            'files_skipped': 0
        }
    }

    # Global settings
    global_settings = config.get('global_settings', {})
    output_dir = Path(global_settings.get('output_directory', 'Converted'))
    skip_if_larger = global_settings.get('skip_if_larger', True)

    if not dry_run:
        output_dir.mkdir(exist_ok=True)
        logger.log(f"Output directory: {output_dir}")

    # Filter already processed files
    if resume:
        already_processed = set(progress['processed_files'].keys()) | set(progress['skipped_files'].keys())
        catalog = [f for f in catalog if f['filepath'] not in already_processed]
        logger.log(f"Resuming: {len(catalog)} files remaining")

    # Process files
    for idx, file_data in enumerate(catalog, 1):
        filepath = file_data['filepath']
        filename = file_data['filename']

        logger.log(f"\n[{idx}/{len(catalog)}] Processing: {filename}")

        # Match strategy
        strategy_name, strategy = match_strategy(file_data, config)

        if not strategy:
            logger.log(f"  No matching strategy found, skipping", "WARN")
            progress['skipped_files'][filepath] = "No matching strategy"
            progress['stats']['files_skipped'] += 1
            continue

        if not strategy.get('enabled', True):
            logger.log(f"  Strategy '{strategy_name}' is disabled, skipping")
            progress['skipped_files'][filepath] = f"Strategy disabled: {strategy_name}"
            progress['stats']['files_skipped'] += 1
            continue

        logger.log(f"  Strategy: {strategy_name}")
        logger.log(f"  Description: {strategy.get('description', 'N/A')}")

        if dry_run:
            logger.log(f"  [DRY RUN] Would process with strategy: {strategy_name}")
            continue

        # Prepare output path
        file_ext = strategy.get('output_format', file_data['file_type']).lower()
        output_filename = Path(filename).stem + '.' + file_ext
        output_path = output_dir / output_filename

        # Avoid overwriting
        counter = 1
        while output_path.exists():
            output_filename = Path(filename).stem + f"_{counter}." + file_ext
            output_path = output_dir / output_filename
            counter += 1

        # Process based on media type
        original_size_mb = float(file_data['file_size_mb'])

        if file_data['media_type'] == 'image':
            success, error = process_image(filepath, str(output_path), strategy, logger)
        elif file_data['media_type'] == 'video':
            success, error = process_video(filepath, str(output_path), strategy, logger)
        else:
            logger.log(f"  Unknown media type: {file_data['media_type']}", "ERROR")
            continue

        if not success:
            logger.log(f"  FAILED: {error}", "ERROR")
            progress['failed_files'][filepath] = error
            progress['stats']['files_failed'] += 1
            continue

        # Validate output
        valid, result = validate_output(str(output_path), original_size_mb, skip_if_larger, logger)

        if not valid:
            logger.log(f"  Validation failed: {result}", "WARN")
            progress['skipped_files'][filepath] = result
            progress['stats']['files_skipped'] += 1
            continue

        # Success!
        output_size_mb = result
        progress['processed_files'][filepath] = {
            'output_path': str(output_path),
            'original_size_mb': original_size_mb,
            'converted_size_mb': output_size_mb,
            'strategy': strategy_name,
            'processed_at': datetime.now().isoformat()
        }

        progress['stats']['files_processed'] += 1
        progress['stats']['total_original_size_mb'] += original_size_mb
        progress['stats']['total_converted_size_mb'] += output_size_mb

        logger.log(f"  SUCCESS: {output_path}")

        # Save progress every 5 files
        if idx % 5 == 0:
            save_progress(progress)

    # Final save
    save_progress(progress)

    # Print summary
    logger.log("\n" + "=" * 70)
    logger.log("PROCESSING COMPLETE")
    logger.log("=" * 70)

    stats = progress['stats']
    logger.log(f"Files processed: {stats['files_processed']}")
    logger.log(f"Files failed: {stats['files_failed']}")
    logger.log(f"Files skipped: {stats['files_skipped']}")

    if stats['files_processed'] > 0:
        orig_size = stats['total_original_size_mb']
        conv_size = stats['total_converted_size_mb']
        saved = orig_size - conv_size
        percent = (saved / orig_size) * 100 if orig_size > 0 else 0

        logger.log(f"\nOriginal size: {orig_size / 1024:.2f} GB")
        logger.log(f"Converted size: {conv_size / 1024:.2f} GB")
        logger.log(f"Space saved: {saved / 1024:.2f} GB ({percent:.1f}%)")

    logger.log("=" * 70)
    logger.close()


if __name__ == "__main__":
    import sys

    # Check for required dependencies
    try:
        subprocess.run(['exiftool', '-ver'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: exiftool is required but not found.")
        print("Install with: brew install exiftool")
        print("\nexiftool is essential for preserving photo dates and metadata.")
        sys.exit(1)

    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ERROR: ffmpeg is required but not found.")
        print("Install with: brew install ffmpeg")
        sys.exit(1)

    dry_run = '--dry-run' in sys.argv
    no_resume = '--no-resume' in sys.argv

    if dry_run:
        print("Running in DRY RUN mode - no files will be modified")

    if no_resume and Path(PROGRESS_FILE).exists():
        os.remove(PROGRESS_FILE)
        print("Starting fresh (ignoring previous progress)")

    try:
        process_files(dry_run=dry_run, resume=not no_resume)
    except KeyboardInterrupt:
        print("\n\nInterrupted! Progress has been saved.")
        print("Run the script again to resume from where you left off.")
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
