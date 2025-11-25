# iCloud Photo Compressor

**Intelligent photo and video compression for iCloud storage optimization.**

A Python toolkit that analyzes, compresses, and optimizes your photo library while preserving metadata, dates, and quality. Perfect for freeing up iCloud storage without losing your memories.

## 🎯 What It Does

- **Analyzes** your entire photo/video library and catalogs metadata
- **Generates** smart compression strategies based on file types and resolutions
- **Processes** files in batch with configurable quality settings
- **Preserves** EXIF metadata, dates, GPS coordinates, and camera info
- **Validates** every conversion (skips if result is larger than original)
- **Resumes** from interruptions - never lose progress

## 📊 Typical Results

Based on real-world testing with 3,500+ photos:
- **Original size**: ~15 GB
- **Compressed size**: ~7 GB
- **Space saved**: ~8 GB (50-55%)
- **Quality**: Visually indistinguishable for most photos

## ⚠️ Important Disclaimers

**This tool is NOT for beginners.** It requires:
- Comfort with command line/terminal
- Understanding of photo formats and compression
- Careful backup practices
- Patience with large-scale processing

**What you'll lose:**
- Live Photos functionality (splits into separate photo + video)
- Photo edits stored in Photos app (only original files are processed)
- Albums, favorites, and other Photos app organization
- Portrait mode depth data (for re-editing blur)
- Slow motion video metadata
- Burst photo grouping

**Before starting:**
- ✅ Backup everything multiple times
- ✅ Test with a small batch first
- ✅ Verify results before deleting originals
- ✅ Have patience - processing thousands of files takes time

## 🚀 Quick Start

### Prerequisites

**macOS** (tested), Linux (should work), Windows (not tested)

```bash
# Install system dependencies
brew install ffmpeg exiftool

# Install Python dependencies
pip install -r requirements.txt
```

### Workflow Overview

```
1. Export photos from iCloud/Photos → Originals/ folder
2. python3 analyze.py              → Scan and catalog files
3. python3 generate_config.py      → Create compression strategies
4. Edit compression_config.yaml    → Review and customize settings
5. python3 process.py --dry-run    → Test without modifying files
6. python3 process.py              → Actually compress files
7. Import Converted/ → Photos app  → Upload to iCloud
8. Delete old photos from iCloud   → Free up space
```

## 📖 Detailed Instructions

### Step 1: Export Your Photos

**Option A: From Photos app (Mac)**
1. Open Photos app
2. Select all photos (Cmd+A) or choose specific ones
3. File → Export → Export Unmodified Original
4. Save to `Originals/` folder in this project

**Option B: From iCloud.com**
1. Go to iCloud.com → Photos
2. Select photos and click download
3. Save to `Originals/` folder

**Option C: Use iCloud Drive sync**
- If photos are already in iCloud Drive, just point to that folder

### Step 2: Analyze Your Media

```bash
python3 analyze.py
```

**What it does:**
- Scans all images (.jpg, .png, .heic) and videos (.mov, .mp4)
- Extracts resolution, file size, codec, bitrate, duration
- Creates `media_catalog.csv` with all metadata
- Shows summary statistics

**Output:**
```
Found 3579 media files
Processing: IMG_0001.HEIC
  Type: image
  Resolution: 4032x3024
  Size: 2.5 MB
...
Total files: 3579
Images: 2596
Videos: 983
Total size: 15.4 GB
```

**Resume capability:** Press Ctrl+C to stop, run again to resume.

### Step 3: Generate Compression Strategies

```bash
python3 generate_config.py
```

**What it does:**
- Groups files by type, resolution, and codec
- Suggests optimal compression settings for each group
- Creates `compression_config.yaml`

**Example output:**
```
image_strategy_01:
  Files: 1435
  Type: HEIF
  Resolution: 4032x3024 (uhd_8k_plus)
  Avg size: 2.8 MB
  Strategy: HEIF images at uhd_8k_plus - downsample to 2048px

video_strategy_01:
  Files: 441
  Type: MOV
  Codec: hevc
  Resolution: 1920x1080 (fhd_1080p)
  Avg size: 45.2 MB
  Strategy: hevc videos at fhd_1080p - optimize compression
```

### Step 4: Review and Customize Configuration

Open `compression_config.yaml` and adjust settings:

```yaml
global_settings:
  output_directory: Converted
  preserve_originals: true       # Never modifies originals
  skip_if_larger: true           # Skip if compressed > original
  log_level: INFO

image_strategies:
  image_strategy_01:
    matches:
      file_type: HEIF
      resolution_category: uhd_8k_plus
      exact_resolution: "4032x3024"
    strategy:
      enabled: true              # Set false to skip this strategy
      output_format: jpeg        # jpeg, png
      quality: 85                # 1-100 (85-95 recommended)
      max_dimension: 2048        # Max width/height in pixels
      description: "4K HEIC → 2048px JPEG"

video_strategies:
  video_strategy_01:
    matches:
      file_type: MOV
      codec: hevc
      resolution_category: fhd_1080p
    strategy:
      enabled: true
      output_format: mp4
      video_codec: libx264       # libx264, libx265
      audio_codec: aac
      crf: 23                    # 18-28 (lower=better quality)
      preset: medium             # fast, medium, slow
      max_resolution: null       # e.g. "1920x1080" to downscale
```

**Quality Guidelines:**

**Images:**
- `quality: 95` - Highest quality, minimal compression
- `quality: 85` - Great quality, good compression (recommended)
- `quality: 75` - Acceptable quality, maximum compression

**Videos:**
- `crf: 18` - Very high quality, larger files
- `crf: 23` - High quality, good compression (recommended)
- `crf: 28` - Good quality, maximum compression

### Step 5: Test with Dry Run

```bash
python3 process.py --dry-run
```

**What it does:**
- Shows what WOULD be processed
- No files are created or modified
- Validates configuration
- Estimates results

**Check the output:**
```
[1/3579] Processing: IMG_0001.HEIC
  Strategy: image_strategy_01
  Description: 4K HEIC → 2048px JPEG
  [DRY RUN] Would process with strategy: image_strategy_01
```

### Step 6: Process Files

```bash
python3 process.py
```

**What it does:**
- Processes each file according to strategies
- Compresses images with Pillow
- Re-encodes videos with ffmpeg
- **Preserves all EXIF metadata** (dates, GPS, camera info)
- Validates each result
- Saves progress every 5 files

**Output:**
```
[1/3579] Processing: IMG_0001.HEIC
  Strategy: image_strategy_01
  Resized to 1536x2048
  EXIF metadata copied
  Original: 2.5 MB → Converted: 0.8 MB
  Size reduction: 68.0%
  SUCCESS: Converted/IMG_0001.jpeg

[2/3579] Processing: VIDEO_0001.MOV
  Strategy: video_strategy_01
  Running ffmpeg with metadata preservation
  Video metadata copied with exiftool
  Original: 45.2 MB → Converted: 18.3 MB
  Size reduction: 59.5%
  SUCCESS: Converted/VIDEO_0001.mp4
...

PROCESSING COMPLETE
Files processed: 3450
Files failed: 8
Files skipped: 121

Original size: 15.4 GB
Converted size: 6.8 GB
Space saved: 8.6 GB (55.8%)
```

**Resume capability:** Press Ctrl+C to stop. Run again to resume from where you stopped.

**Logging:** Everything is logged to `process_log.txt` for review.

### Step 7: Verify Results

**Check a sample of converted files:**
```bash
# Open a few converted images/videos
open Converted/IMG_0001.jpeg
open Converted/VIDEO_0001.mp4
```

**Verify metadata was preserved:**
```bash
# Check dates on a converted file
exiftool Converted/IMG_0001.jpeg | grep Date

# Compare with original
exiftool Originals/IMG_0001.HEIC | grep Date
```

**Check statistics:**
```bash
# Review the detailed log
less process_log.txt

# Check progress file for stats
cat process_progress.json
```

### Step 8: Import to Photos App

**Option A: Drag and drop**
1. Open Photos app
2. Drag `Converted/` folder into Photos
3. Wait for import to complete

**Option B: File → Import**
1. Open Photos app
2. File → Import
3. Select `Converted/` folder
4. Click "Import All"

**Photos will:**
- Sort by the preserved date metadata
- Maintain chronological order
- Preserve GPS locations
- Upload to iCloud automatically (if enabled)

### Step 9: Delete Old Photos from iCloud

**⚠️ CRITICAL: Only after verifying new photos uploaded successfully!**

1. Check iCloud Photos has all new photos
2. Verify a sample of dates/locations are correct
3. Delete old photos from iCloud via:
   - iCloud.com → Photos → Select All → Delete
   - Photos app → Delete from Mac and iCloud
4. Empty "Recently Deleted" album to free space

**Storage should now be significantly reduced!**

## 🛠️ Advanced Usage

### Custom Output Directory

Edit `compression_config.yaml`:
```yaml
global_settings:
  output_directory: /path/to/custom/output
```

### Process Only Specific File Types

Disable strategies you don't want:
```yaml
strategy:
  enabled: false  # This strategy will be skipped
```

### Start Fresh (Ignore Previous Progress)

```bash
python3 analyze.py --no-resume
python3 process.py --no-resume
```

### Process in Stages

```bash
# Process only first 100 files, then review
# Edit compression_config.yaml to disable strategies for already-processed types
python3 process.py
# Stop after 100 files (Ctrl+C)
# Review results in Converted/
# Continue processing
python3 process.py
```

## 🐛 Troubleshooting

### "exiftool not found"
```bash
brew install exiftool
```
exiftool is **required** for preserving dates and metadata.

### "ffmpeg not found"
```bash
brew install ffmpeg
```

### "HEIC files can't be opened"
```bash
pip install pillow-heif
```

### Photos Import in Wrong Order
The dates should be preserved. Check:
```bash
exiftool Converted/IMG_0001.jpeg | grep Date
```
If dates are missing, there was an issue during processing.

### Converted Files Are Larger
This is normal for already-compressed files. The script skips them automatically if `skip_if_larger: true`.

### Processing is Slow
Video re-encoding is CPU-intensive:
- Use `preset: fast` for faster processing (larger files)
- Use `preset: slow` for better compression (takes longer)
- Process overnight for large libraries

### Out of Disk Space
Processing creates new files, you need:
- At least 50-70% of original library size
- Or enable `skip_if_larger: true` and process will use less space

## 📁 File Structure

```
icloud-photo-compressor/
├── analyze.py                  # Step 1: Scan and catalog
├── generate_config.py          # Step 2: Generate strategies
├── process.py                  # Step 3: Batch process
├── requirements.txt            # Python dependencies
└── README.md                   # This file

# Files created during processing:
Originals/                      # Your original media (input)
Converted/                      # Processed files (output)
media_catalog.csv               # Catalog of all files
compression_config.yaml         # Editable compression strategies
analyze_progress.json           # Analysis progress tracker
process_progress.json           # Processing progress tracker
process_log.txt                 # Detailed processing log
```

## 🎓 Understanding Compression

### Image Compression

**HEIC → JPEG:**
- HEIC is Apple's modern format (efficient but not universal)
- JPEG is universal but less efficient
- Converting HEIC to JPEG usually increases size slightly
- Downsampling resolution compensates and saves space

**Resolution Downsampling:**
- 4K photo (4032x3024) = 12 megapixels
- 2K photo (2048x1536) = 3 megapixels
- Most screens are 1080p-4K, so 2048px is plenty for viewing
- Downsampling 4K → 2K saves ~60-70% space

**Quality Settings:**
- JPEG quality 85-95 is visually indistinguishable for most people
- Below 80 shows visible compression artifacts
- Above 95 creates large files with minimal quality gain

### Video Compression

**Codecs:**
- H.264 (libx264): Universal, efficient, compatible everywhere
- H.265 (libx265): More efficient but less compatible

**CRF (Constant Rate Factor):**
- Lower = better quality, larger files
- Higher = worse quality, smaller files
- 18-28 is the useful range
- 23 is a good balance

**Preset:**
- `fast`: Quick encoding, larger files
- `medium`: Balanced (default)
- `slow`: Better compression, takes longer
- Doesn't affect quality, only encoding efficiency

## 🔒 Privacy & Security

- All processing is done locally on your machine
- No data is sent to any server or cloud service
- Your photos never leave your computer
- Open source - you can review all code

## 🤝 Contributing

Found a bug? Have a feature request? Open an issue!

Want to contribute? Pull requests welcome.

## 📜 License

MIT License - Free to use and modify.

## ⚠️ Final Warning

**This tool modifies your photo library workflow. Use at your own risk.**

- Always maintain backups
- Test with small batches first
- Verify results before deleting originals
- Understand what you're losing (Live Photos, edits, albums)

**The author is not responsible for any data loss.**

## 💡 Tips for Success

1. **Start small**: Test with 50-100 photos first
2. **Check quality**: Open several converted files and verify they look good
3. **Verify dates**: Make sure dates are preserved before processing all files
4. **Be patient**: Processing 3000+ files takes hours
5. **Monitor progress**: Check `process_log.txt` periodically
6. **Keep originals**: Don't delete originals until you're 100% satisfied

## 🎉 Success Story

This tool was created to compress a personal library of 3,500+ photos and videos from iCloud. Results:

- ✅ Saved 8.6 GB of iCloud storage
- ✅ Maintained visual quality
- ✅ Preserved all dates and locations
- ✅ Successfully re-uploaded to iCloud
- ✅ Photos sorted correctly by date
- ✅ No data loss

Your results may vary based on your library composition and settings.

---

**Questions?** Open an issue on GitHub.

**Like this tool?** Give it a star! ⭐
