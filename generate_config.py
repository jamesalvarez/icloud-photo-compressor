#!/usr/bin/env python3
"""
Configuration Generator - Analyzes media catalog and generates compression strategies
Creates an editable YAML config file with suggested compression settings
"""

import csv
import yaml
from collections import defaultdict
from pathlib import Path

# Configuration
INPUT_CSV = "media_catalog.csv"
OUTPUT_CONFIG = "compression_config.yaml"


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
    elif pixels <= 640 * 480:  # SD
        return "sd_480p"
    elif pixels <= 960 * 720:  # HD
        return "hd_720p"
    elif pixels <= 1920 * 1080:  # Full HD
        return "fhd_1080p"
    elif pixels <= 2560 * 1440:  # 2K
        return "qhd_1440p"
    elif pixels <= 3840 * 2160:  # 4K
        return "uhd_4k"
    else:  # 8K and above
        return "uhd_8k_plus"


def suggest_image_strategy(file_type, width, height, avg_size_mb, count):
    """Suggest compression strategy for images"""
    res_category = get_resolution_category(width, height)

    # Base strategy
    strategy = {
        'enabled': True,
        'output_format': 'jpeg',  # Default to JPEG for compatibility
        'quality': 85,
        'max_dimension': None,
        'description': f"{file_type} images at {res_category} resolution"
    }

    # Adjust based on resolution category
    if res_category in ['uhd_4k', 'uhd_8k_plus']:
        strategy['max_dimension'] = 2048
        strategy['quality'] = 85
        strategy['description'] += " - downsample to 2048px for web/mobile use"
    elif res_category == 'qhd_1440p':
        strategy['max_dimension'] = 1920
        strategy['quality'] = 85
        strategy['description'] += " - downsample to 1920px"
    elif res_category == 'fhd_1080p':
        strategy['quality'] = 85
        strategy['description'] += " - maintain size, optimize quality"
    else:
        strategy['quality'] = 90
        strategy['description'] += " - maintain size, high quality"

    # For HEIC files, suggest converting to JPEG
    if file_type.upper() == 'HEIC':
        strategy['output_format'] = 'jpeg'
        strategy['description'] += " (convert HEIC to JPEG for compatibility)"

    # For PNG files with reasonable size, keep as PNG
    if file_type.upper() == 'PNG' and avg_size_mb < 2:
        strategy['output_format'] = 'png'
        strategy['quality'] = 90
        strategy['description'] += " (keep as PNG for transparency)"

    return strategy


def suggest_video_strategy(file_type, codec, width, height, avg_size_mb, avg_bitrate_mbps, count):
    """Suggest compression strategy for videos"""
    res_category = get_resolution_category(width, height)

    # Base strategy
    strategy = {
        'enabled': True,
        'output_format': 'mp4',
        'video_codec': 'libx264',
        'audio_codec': 'aac',
        'crf': 23,  # Constant Rate Factor (lower = better quality, 18-28 typical range)
        'preset': 'medium',
        'max_resolution': None,
        'target_bitrate': None,
        'description': f"{codec} videos at {res_category} resolution"
    }

    # Adjust based on resolution
    if res_category in ['uhd_4k', 'uhd_8k_plus']:
        strategy['crf'] = 24
        strategy['max_resolution'] = '1920x1080'
        strategy['preset'] = 'slow'
        strategy['description'] += " - downsample to 1080p for compatibility"
    elif res_category == 'qhd_1440p':
        strategy['crf'] = 23
        strategy['max_resolution'] = '1920x1080'
        strategy['preset'] = 'medium'
        strategy['description'] += " - downsample to 1080p"
    elif res_category == 'fhd_1080p':
        strategy['crf'] = 23
        strategy['preset'] = 'medium'
        strategy['description'] += " - maintain resolution, optimize compression"
    else:
        strategy['crf'] = 22
        strategy['preset'] = 'fast'
        strategy['description'] += " - maintain resolution"

    # Use H.265 for better compression if not already
    if codec.lower() not in ['hevc', 'h265']:
        strategy['video_codec'] = 'libx265'
        strategy['crf'] = 28  # H.265 can use higher CRF for same quality
        strategy['description'] += " (encode to H.265 for better compression)"

    return strategy


def generate_config():
    """Main function to generate compression configuration"""
    print("=" * 70)
    print("COMPRESSION STRATEGY GENERATOR")
    print("=" * 70)

    # Read catalog
    if not Path(INPUT_CSV).exists():
        print(f"Error: {INPUT_CSV} not found!")
        print("Please run analyze.py first.")
        return

    with open(INPUT_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Read {len(rows)} entries from catalog")

    # Filter out errors
    valid_rows = [r for r in rows if not r.get('error')]
    print(f"Valid entries: {len(valid_rows)}")

    # Group images by type and resolution category
    image_groups = defaultdict(list)
    video_groups = defaultdict(list)

    for row in valid_rows:
        width, height = parse_resolution(row.get('resolution'))
        res_category = get_resolution_category(width, height)

        if row['media_type'] == 'image':
            key = (row['file_type'], res_category, width, height)
            image_groups[key].append(row)
        elif row['media_type'] == 'video':
            codec = row.get('codec', 'unknown')
            key = (row['file_type'], codec, res_category, width, height)
            video_groups[key].append(row)

    print(f"\nFound {len(image_groups)} unique image groups")
    print(f"Found {len(video_groups)} unique video groups")

    # Generate strategies
    config = {
        'version': '1.0',
        'description': 'Auto-generated compression strategies. Edit as needed.',
        'global_settings': {
            'output_directory': 'Converted',
            'preserve_originals': True,
            'skip_if_larger': True,
            'log_level': 'INFO'
        },
        'image_strategies': {},
        'video_strategies': {}
    }

    # Image strategies
    print("\n" + "=" * 70)
    print("IMAGE STRATEGIES")
    print("=" * 70)

    for idx, (key, files) in enumerate(sorted(image_groups.items(), key=lambda x: len(x[1]), reverse=True), 1):
        file_type, res_category, width, height = key
        count = len(files)
        avg_size_mb = sum(float(f['file_size_mb']) for f in files) / count

        strategy_name = f"image_strategy_{idx:02d}"
        strategy = suggest_image_strategy(file_type, width, height, avg_size_mb, count)

        print(f"\n{strategy_name}:")
        print(f"  Files: {count}")
        print(f"  Type: {file_type}")
        print(f"  Resolution: {width}x{height} ({res_category})")
        print(f"  Avg size: {avg_size_mb:.2f} MB")
        print(f"  Strategy: {strategy['description']}")

        config['image_strategies'][strategy_name] = {
            'matches': {
                'file_type': file_type,
                'resolution_category': res_category,
                'exact_resolution': f"{width}x{height}",
                'file_count': count
            },
            'strategy': strategy
        }

    # Video strategies
    print("\n" + "=" * 70)
    print("VIDEO STRATEGIES")
    print("=" * 70)

    for idx, (key, files) in enumerate(sorted(video_groups.items(), key=lambda x: len(x[1]), reverse=True), 1):
        file_type, codec, res_category, width, height = key
        count = len(files)
        avg_size_mb = sum(float(f['file_size_mb']) for f in files if f.get('file_size_mb')) / count
        avg_bitrate = sum(float(f.get('bitrate_mbps', 0)) for f in files if f.get('bitrate_mbps') != 'N/A') / count

        strategy_name = f"video_strategy_{idx:02d}"
        strategy = suggest_video_strategy(file_type, codec, width, height, avg_size_mb, avg_bitrate, count)

        print(f"\n{strategy_name}:")
        print(f"  Files: {count}")
        print(f"  Type: {file_type}")
        print(f"  Codec: {codec}")
        print(f"  Resolution: {width}x{height} ({res_category})")
        print(f"  Avg size: {avg_size_mb:.2f} MB")
        print(f"  Avg bitrate: {avg_bitrate:.2f} Mbps")
        print(f"  Strategy: {strategy['description']}")

        config['video_strategies'][strategy_name] = {
            'matches': {
                'file_type': file_type,
                'codec': codec,
                'resolution_category': res_category,
                'exact_resolution': f"{width}x{height}",
                'file_count': count
            },
            'strategy': strategy
        }

    # Write config file
    with open(OUTPUT_CONFIG, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    print("\n" + "=" * 70)
    print(f"Configuration saved to {OUTPUT_CONFIG}")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Review and edit the configuration file as needed")
    print("2. Adjust quality settings, output formats, or enable/disable strategies")
    print("3. Run process.py to start batch processing")
    print("=" * 70)


if __name__ == "__main__":
    try:
        generate_config()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
