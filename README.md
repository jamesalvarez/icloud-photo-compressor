# iCloud Photo Compressor

Python scripts for compressing photos and videos to save iCloud storage space. Tested on ~3,500 files, saved about 55% storage (15GB to 7GB).

**Warning: This was vibe coded - it worked for me, but buyer beware!**

## What it does

- Scans your photo library and catalogs everything
- Generates compression strategies based on file types and resolutions
- Batch processes files while preserving EXIF metadata (dates, GPS, etc.)
- Validates conversions and skips if compressed file is larger
- Can resume if interrupted

## Not for beginners

You need to be comfortable with terminal/command line and understand what you're doing. This workflow involves deleting your entire iCloud photo library and re-uploading compressed versions.

## What you'll lose

- Live Photos (become separate photo + video files)
- Any edits you made in Photos app
- Albums, favorites, face tags, keywords
- Portrait mode depth data
- Slow motion metadata
- Burst groupings

If you care about any of these, this tool isn't for you.

## CRITICAL: Backup first

Before doing anything:

1. **Export ALL your photos** to an external hard drive
2. **Make a second backup** to another location (cloud drive, another external drive, whatever)
3. **Verify both backups** actually have all your photos
4. **Test opening files** from the backup to make sure they're not corrupted

Do NOT proceed until you have TWO complete backups of your originals.

## Workflow

### 1. Setup

Install dependencies (macOS):
```bash
brew install ffmpeg exiftool
pip install -r requirements.txt
```

### 2. Export your photos

Export everything to an `Originals/` folder in the same directory as these scripts:
- Photos app: File → Export → Export Unmodified Original
- Save all files to `Originals/` folder

### 3. Run the scripts

```bash
# Analyze your library
python3 analyze.py

# Generate compression strategies
python3 generate_config.py

# Edit compression_config.yaml if you want to customize

# Test run (doesn't modify anything)
python3 process.py --dry-run

# Actually process files
python3 process.py
```

Processing 3,500 files takes a few hours. You can stop it (Ctrl+C) and resume later.

### 4. Verify results

Check some files in `Converted/` folder:
- Open a few images/videos and make sure quality is acceptable
- Check dates are preserved: `exiftool Converted/IMG_0001.jpeg | grep Date`
- Compare file sizes

If anything looks wrong, stop here. Don't delete your originals.

### 5. Delete everything from iCloud and devices

To avoid headaches - you need to start with a completely empty iCloud Photos library on your devices and on icloud.  This is because you will otherwise end up with two photos and not an easy way to tell which is compressed and which is not.

1. **Delete from iCloud.com**: Go to iCloud.com → Photos → Select All → Delete
2. **Empty Recently Deleted** on iCloud.com
3. **On your iPhone/iPad**: Settings → Apple ID → iCloud → Photos → Turn OFF "Sync this iPhone" → Choose "Remove from iPhone"
4. **On your Mac**: Photos app → delete everything → empty Recently Deleted

Wait for everything to sync and confirm iCloud Photos is completely empty. Check on multiple devices.

### 6. Import compressed photos

Now import the `Converted/` folder to Photos app on the Mac:
- Open Photos app (it should be empty)
- File → Import
- Select `Converted/` folder
- Import all

Photos will upload to iCloud automatically if sync is enabled. This will take a while.

### 7. Done

Your iCloud storage should now show significantly less usage. Check:
- Settings → Apple ID → iCloud → Manage Storage → Photos

Photos should sync back down to your iPhone/iPad automatically.

## Configuration

The `compression_config.yaml` file controls how files are compressed. Defaults are reasonable but you can adjust:

**For images:**
- `quality: 85` - Good balance (1-100 scale)
- `max_dimension: 2048` - Downsample large photos to 2048px max
- `output_format: jpeg` - Universal compatibility

**For videos:**
- `crf: 23` - Quality setting (18=high quality, 28=smaller files)
- `preset: medium` - Encoding speed (fast/medium/slow)
- `video_codec: libx264` - H.264 codec for compatibility

Higher quality = larger files. Lower quality = smaller files but visible compression.

## What gets preserved

- EXIF dates (creation date, modified date)
- GPS coordinates
- Camera model and settings
- Most other metadata

## What doesn't get preserved

- Live Photos pairing
- Portrait mode depth maps
- Slow motion markers
- Burst groupings
- Photos app edits
- Albums and organization

## Files created

```
Originals/                  # Your original files (don't delete until verified)
Converted/                  # Processed files ready to import
media_catalog.csv           # Catalog of all files
compression_config.yaml     # Your compression settings
analyze_progress.json       # Progress tracking
process_progress.json       # Processing state
process_log.txt            # Detailed log
```

## Why this works

iCloud Photos sorts by EXIF date, not file system date. The scripts preserve all EXIF metadata including dates, so photos import in the correct chronological order.

Modern phone cameras create huge files (3-5MB photos, 50+MB videos). Most of that quality is wasted on screens. Downsampling 4K photos to 2K and re-encoding videos with better compression saves massive space with minimal visible quality loss.

## License

MIT - Use at your own risk. Not responsible for data loss.
