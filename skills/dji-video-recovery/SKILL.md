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
  - DJI video
  - drone video
  - SD card
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
---

# DJI Video Recovery Skill

Recover accidentally deleted DJI drone video files from ExFAT SD cards using FAT chain recovery and moov atom matching.

## Prerequisites Check

Before starting recovery, verify the environment:

1. **Detect SD card**: Run `diskutil list external` to find the SD card device (e.g., `/dev/disk4`, `/dev/disk5`)
2. **Verify ExFAT**: Run `diskutil info /dev/diskNs1` and confirm `Type (Bundle): exfat`
3. **Grant read access**: Run `sudo chmod o+r /dev/rdiskNs1` (use the raw device `rdisk`)
4. **Check ffmpeg**: Run `which ffmpeg` — install with `brew install ffmpeg` if missing
5. **Check Python**: Run `python3 --version` — need 3.8+

If any prerequisite fails, tell the user what to install/fix before proceeding.

## Phase 1: SD Card Analysis

Gather ExFAT filesystem parameters from the boot sector:

```bash
diskutil info /dev/diskNs1

sudo python3 -c "
import struct
with open('/dev/rdiskNs1', 'rb') as f:
    bs = f.read(512)
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

## Phase 2: FAT Chain Recovery

Run the core recovery script:

```bash
sudo python3 ${SKILL_DIR}/scripts/fat_chain_recover.py /dev/rdiskNs1 ~/Desktop/sd_recovery/
```

The script will:
1. Read the ExFAT boot sector and detect all filesystem parameters automatically
2. Parse the FAT table to find cluster chains
3. Identify MP4 chains (those starting with `ftyp` atom)
4. Reconstruct files by reading clusters in chain order
5. Scan the entire disk for orphaned `moov` atoms
6. Match moov atoms to incomplete files using NAL unit validation
7. Append matched moov atoms to make files playable

## Phase 3: Verification

Verify recovered files with ffmpeg:

```bash
# Quick sample check
cd ~/Desktop/sd_recovery/
for fn in $(ls *.mp4 | head -5); do
    echo "=== $fn ==="
    ffmpeg -err_detect ignore_err -i "$fn" -f null - 2>&1 | grep -E "frame=|Duration"
done

# Full batch verification
python3 ${SKILL_DIR}/scripts/verify_recovery.py ~/Desktop/sd_recovery/
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
macOS requires 512-byte aligned reads on raw devices. The recovery script handles this internally with `aligned_read()`.

### Files have ftyp+mdat but no moov
- The video was interrupted before moov was written
- Try scanning for moov atoms with a wider range
- These files are partially recoverable — the first few seconds may play

### moov matching gives wrong results
- Increase validation strictness (require score >= 100 instead of 80)
- Add secondary validation: check that moov's total video size matches file size

## Important Notes

- **NEVER write to the SD card** — only read from it
- **Do not modify FAT or boot sectors** — this could destroy remaining data
- The recovery scripts only READ from the disk device
- All output goes to a directory on the local machine
