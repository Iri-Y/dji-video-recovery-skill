---
name: dji-video-recovery
description: Recover accidentally deleted DJI drone video files from ExFAT SD cards using FAT chain recovery and moov atom matching
triggers:
  - deleted video
  - SD card recovery
  - DJI recovery
  - recover mp4
  - video recovery
  - restore video
---

# DJI Video Recovery Skill

You are helping the user recover accidentally deleted DJI drone video files from an ExFAT SD card. Follow this workflow precisely.

## Prerequisites Check

Before starting, verify:

1. **Detect SD card**: Run `diskutil list external` to find the SD card device (e.g., `/dev/disk4`, `/dev/disk5`)
2. **Verify ExFAT**: Run `diskutil info /dev/diskNs1` and confirm `Type (Bundle): exfat`
3. **Grant read access**: Run `sudo chmod o+r /dev/rdiskNs1` (use the raw device `rdisk`)
4. **Check ffmpeg**: Run `which ffmpeg` — install with `brew install ffmpeg` if missing
5. **Check Python**: Run `python3 --version` — need 3.8+

If any prerequisite fails, tell the user what to install/fix before proceeding.

## Phase 1: SD Card Analysis

First, gather information about the SD card:

```bash
# Get disk info
diskutil info /dev/diskNs1

# Verify we can read the raw device
sudo python3 -c "
import struct
with open('/dev/rdiskNs1', 'rb') as f:
    # Read ExFAT boot sector
    f.seek(0)
    bs = f.read(512)
    # Check ExFAT signature
    if bs[3:11] == b'EXFAT   ':
        print('ExFAT confirmed')
    else:
        print('NOT ExFAT!')
        exit(1)

    bytes_per_sector = struct.unpack('<H', bs[11:13])[0]
    sectors_per_cluster = bs[13]
    cluster_size = bytes_per_sector * sectors_per_cluster
    cluster_heap_offset = struct.unpack('<I', bs[44:48])[0] * bytes_per_sector
    cluster_count = struct.unpack('<I', bs[52:56])[0]

    print(f'ClusterSize: {cluster_size}')
    print(f'ClusterHeapOffset: {cluster_heap_offset}')
    print(f'ClusterCount: {cluster_count}')
    print(f'DiskSize: ~{cluster_count * cluster_size / 1024**3:.1f} GB')
"
```

Record these values — they are needed by the recovery scripts.

## Phase 2: FAT Chain Recovery

This is the core recovery step. Use the `fat_chain_recover.py` script:

```bash
# Run the recovery script
sudo python3 /path/to/scripts/fat_chain_recover.py /dev/rdiskNs1 ~/Desktop/sd_recovery/fat_chain_recovery/
```

**Important**: Before running, you MUST update these constants in the script to match the actual SD card:
- `DISK_SIZE`: Total disk size in bytes (from diskutil info)
- `CLUSTER_SIZE`: e.g., 131072 for 128KB clusters
- `SECTOR_SIZE`: Usually 512
- `CLUSTER_HEAP_OFFSET`: From boot sector analysis
- `FAT_OFFSET`: From boot sector (usually sector 128)
- `FAT_LENGTH`: From boot sector (usually 3968 sectors)

Alternatively, read these values dynamically from the ExFAT boot sector.

The script will:
1. Read the FAT table
2. Find all cluster chains starting with `ftyp` (MP4 header)
3. Reconstruct files by reading clusters in chain order
4. Scan the disk for orphaned `moov` atoms
5. Match moov atoms to files that lack them
6. Append matched moov to make files playable

## Phase 3: Verification

After recovery, verify the files are playable:

```bash
# Quick verification of a sample
cd ~/Desktop/sd_recovery/fat_chain_recovery/
for fn in $(ls *.mp4 | head -5); do
    echo "=== $fn ==="
    ffmpeg -err_detect ignore_err -i "$fn" -f null - 2>&1 | grep -E "frame=|Duration"
done
```

Use the batch verification script for all files:

```bash
sudo python3 /path/to/scripts/verify_recovery.py ~/Desktop/sd_recovery/fat_chain_recovery/
```

## Phase 4: Report Results

Report to the user:
- Total files recovered
- Files with moov (playable)
- Files still missing moov
- Total data size
- Longest video duration

## Troubleshooting

### "Permission denied" reading disk
```bash
sudo chmod o+r /dev/rdiskNs1
```

### "Invalid argument" on disk read
macOS requires 512-byte aligned reads on raw devices. The script handles this with `aligned_read()`.

### Files have ftyp+mdat but no moov
The moov matching step should handle this. If no moov matches:
- The video was interrupted before moov was written (recording was cut short)
- Try scanning for moov atoms with a wider range
- These files are partially recoverable — the first few seconds may play

### moov matching gives wrong results
The NAL validation (checking for valid HEVC/H.264 NAL units at stco positions) ensures correct matching. If results are wrong:
- Increase the validation strictness (require score >= 100 instead of 80)
- Add secondary validation: check that moov's total video size ≈ file size

### Disk too large / running out of space
The recovery creates files equal to chain_length × cluster_size. For a 64GB SD card, expect ~45GB of output. Ensure sufficient disk space.

## Key Technical Details

### DJI MP4 File Structure
```
ftyp (28 bytes) + free (8 bytes) + free (464/468 bytes) + mdat (variable) + moov
```

- `ftyp`: File type box, contains "isom" or "qt  " for DJI
- `free`: Padding atoms
- `mdat`: Media data — contains interleaved video (HEVC/H.264), audio (AAC), and DJI metadata (djmd, dbgi, tmcd)
- `moov`: Movie metadata — contains all frame offsets (stco), sizes (stsz), codec params (hvcC/avcC), timestamps, etc.

### Why PhotoRec/foremost Fail
- These tools read sequential disk blocks
- ExFAT often fragments files across non-contiguous clusters
- Sequential reading mixes data from multiple files
- The result: files with correct headers but wrong content after the first fragmentation point

### Why FAT Chain Recovery Works
- ExFAT maintains a FAT (File Allocation Table) that maps each cluster to the next
- Even after deletion, the FAT chains often remain intact
- By following the chain, we read clusters in the correct order
- This produces byte-perfect file reconstructions

### Moov Atom Matching
- DJI writes moov at file end — it's often the last thing written
- If the file was deleted/interrupted, moov's cluster may be freed but data remains on disk
- We scan the entire disk for `moov` signatures
- Match by: checking if the file's data at `stco[0]` offset contains valid HEVC/AVC NAL units
- Score: IDR NAL at expected position = 100 points, non-IDR = 80 points, size consistency = +20 points

## Important Notes

- **NEVER write to the SD card** — only read from it
- **Do not modify FAT or boot sectors** — this could destroy remaining data
- **Warn the user** before any write operations to the disk
- The recovery scripts only READ from the disk device
- All output goes to a directory on the local machine
