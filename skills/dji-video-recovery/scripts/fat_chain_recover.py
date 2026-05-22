#!/usr/bin/env python3
"""
ExFAT FAT Chain MP4 Recovery Tool
Recovers DJI drone video files by following ExFAT FAT cluster chains.

Works by:
1. Reading ExFAT boot sector to get filesystem parameters
2. Following FAT cluster chains to reconstruct files in correct order
3. Scanning disk for orphaned moov atoms and matching to incomplete files
4. Verifying recovered files with NAL unit validation

Usage: sudo python3 fat_chain_recover.py /dev/rdisk4s1 /path/to/output/
"""

import struct, os, sys, time

SECTOR_SIZE = 512


def log(msg):
    print(msg, flush=True)


def aligned_read(fd, offset, size):
    """Read from raw disk device with 512-byte alignment (required on macOS)."""
    aligned_off = (offset // SECTOR_SIZE) * SECTOR_SIZE
    diff = offset - aligned_off
    read_size = ((size + diff + SECTOR_SIZE - 1) // SECTOR_SIZE) * SECTOR_SIZE
    fd.seek(aligned_off)
    return fd.read(read_size)[diff:diff + size]


def parse_exfat_boot_sector(disk_path):
    """Read and parse ExFAT boot sector to get filesystem parameters."""
    with open(disk_path, 'rb') as f:
        bs = f.read(512)

    if bs[3:11] != b'EXFAT   ':
        log(f'ERROR: {disk_path} is not an ExFAT filesystem')
        sys.exit(1)

    params = {
        'bytes_per_sector': struct.unpack('<H', bs[11:13])[0],
        'sectors_per_cluster': bs[13],
        'fat_offset_sectors': struct.unpack('<I', bs[44:48])[0],
        'fat_length_sectors': struct.unpack('<I', bs[48:52])[0],
        'cluster_heap_offset_sectors': struct.unpack('<I', bs[52:56])[0],
        'cluster_count': struct.unpack('<I', bs[56:60])[0],
    }

    params['sector_size'] = params['bytes_per_sector']
    params['cluster_size'] = params['bytes_per_sector'] * params['sectors_per_cluster']
    params['cluster_heap_offset'] = params['cluster_heap_offset_sectors'] * params['sector_size']
    params['fat_offset'] = params['fat_offset_sectors'] * params['sector_size']
    params['fat_length'] = params['fat_length_sectors'] * params['sector_size']

    # Get disk size
    disk_size = 0
    try:
        disk_size = os.path.getsize(disk_path)
    except OSError:
        pass
    if disk_size == 0:
        # Raw devices report 0 via stat; compute from volume length in boot sector
        volume_length_sectors = struct.unpack('<Q', bs[32:40])[0]
        disk_size = volume_length_sectors * params['sector_size']

    params['disk_size'] = disk_size

    log(f'ExFAT Parameters:')
    log(f'  Sector size: {params["sector_size"]} bytes')
    log(f'  Cluster size: {params["cluster_size"]} bytes ({params["cluster_size"] // 1024}KB)')
    log(f'  Cluster count: {params["cluster_count"]}')
    log(f'  Cluster heap offset: {params["cluster_heap_offset"]} bytes')
    log(f'  FAT offset: {params["fat_offset"]} bytes')
    log(f'  FAT length: {params["fat_length"]} bytes')
    log(f'  Disk size: {disk_size / 1024 ** 3:.2f} GB')

    return params


def read_fat(disk_path, params):
    """Read and parse the ExFAT FAT table."""
    with open(disk_path, 'rb') as f:
        f.seek(params['fat_offset'])
        fat_data = f.read(params['fat_length'])

    total_entries = len(fat_data) // 4

    def fat_entry(cluster):
        if cluster < 2 or cluster >= total_entries:
            return None
        off = cluster * 4
        val = struct.unpack('<I', fat_data[off:off + 4])[0]
        if val >= 0xFFFFFFFE:
            return -2  # free
        if val >= 0xFFFFFFFC:
            return -1  # end of chain
        if val == 0:
            return 0
        return val  # next cluster

    return fat_entry, total_entries


def cluster_to_disk_offset(cluster, params):
    """Convert ExFAT cluster number to disk byte offset."""
    return params['cluster_heap_offset'] + (cluster - 2) * params['cluster_size']


def follow_chain(fat_entry, start_cluster, max_len=50000):
    """Follow a FAT cluster chain from start_cluster."""
    chain = [start_cluster]
    cur = start_cluster
    for _ in range(max_len):
        nxt = fat_entry(cur)
        if nxt is None or nxt <= 0:
            break
        chain.append(nxt)
        cur = nxt
    return chain


def find_mp4_chains(disk_path, fat_entry, total_entries, params, min_clusters=5):
    """Find all FAT chains that start with an MP4 ftyp atom."""
    log('Finding orphan chain starts...')

    pointed_to = set()
    for cl in range(2, total_entries):
        fe = fat_entry(cl)
        if fe is not None and fe > 0 and fe < 0xFFFFFFFC:
            pointed_to.add(fe)

    chain_starts = [cl for cl in range(2, total_entries)
                    if fat_entry(cl) is not None and fat_entry(cl) > 0
                    and fat_entry(cl) < 0xFFFFFFFC and cl not in pointed_to]

    log(f'Found {len(chain_starts)} orphan chain starts')

    mp4_chains = []
    with open(disk_path, 'rb') as f:
        for start in chain_starts:
            chain = follow_chain(fat_entry, start)
            if len(chain) < min_clusters:
                continue

            disk_pos = cluster_to_disk_offset(start, params)
            header = aligned_read(f, disk_pos, 12)

            if len(header) >= 8 and header[4:8] == b'ftyp':
                data_size = len(chain) * params['cluster_size']
                mp4_chains.append((len(chain), data_size, start, chain))

    mp4_chains.sort(key=lambda x: -x[0])
    log(f'Found {len(mp4_chains)} MP4 chains with ftyp header')
    return mp4_chains


def reconstruct_file(disk_path, chain, output_path, params):
    """Reconstruct a file from its FAT cluster chain."""
    with open(disk_path, 'rb') as df:
        with open(output_path, 'wb') as out:
            for cl in chain:
                disk_pos = cluster_to_disk_offset(cl, params)
                data = aligned_read(df, disk_pos, params['cluster_size'])
                out.write(data)


def check_moov_in_file(filepath):
    """Check if a file contains a moov atom near the end."""
    with open(filepath, 'rb') as f:
        f.seek(0, 2)
        fsize = f.tell()
        f.seek(max(0, fsize - 2 * 1024 * 1024))
        tail = f.read(2 * 1024 * 1024)
        return tail.rfind(b'moov') >= 0


def scan_moov_atoms(disk_path, params):
    """Scan entire disk for moov atoms, return list of (offset, size)."""
    log('Scanning disk for moov atoms...')
    moov_list = []
    chunk_size = 50 * 1024 * 1024  # 50MB
    disk_size = params['disk_size']

    with open(disk_path, 'rb') as f:
        offset = 0
        overlap = 8

        while offset < disk_size:
            f.seek((offset // SECTOR_SIZE) * SECTOR_SIZE)
            data = f.read(chunk_size + overlap)
            if not data:
                break

            pos = 0
            while True:
                idx = data.find(b'moov', pos)
                if idx == -1:
                    break
                disk_pos = offset + idx
                if idx >= 4:
                    moov_size = struct.unpack('>I', data[idx - 4:idx])[0]
                    if 1000 < moov_size < 50000000:
                        moov_list.append((disk_pos - 4, moov_size))
                pos = idx + 1

            offset += chunk_size
            if offset % (5 * 1024 ** 3) < chunk_size:
                log(f'  {offset / 1024 ** 3:.1f}GB / {disk_size / 1024 ** 3:.1f}GB, {len(moov_list)} moovs')

    log(f'Found {len(moov_list)} moov atoms')
    return moov_list


def parse_moov_info(disk_path, moov_list):
    """Parse moov atoms to extract video track metadata for matching."""
    log('Parsing moov atoms...')
    results = []

    with open(disk_path, 'rb') as fd:
        for disk_off, moov_size in moov_list:
            try:
                moov_data = aligned_read(fd, disk_off, min(moov_size, 5000000))
                if len(moov_data) < 100 or moov_data[4:8] != b'moov':
                    continue

                stco_pos = moov_data.find(b'stco')
                if stco_pos < 0 or stco_pos + 16 > len(moov_data):
                    continue

                entry_count = struct.unpack('>I', moov_data[stco_pos + 8:stco_pos + 12])[0]
                if entry_count < 1 or entry_count > 100000:
                    continue

                first_stco = struct.unpack('>I', moov_data[stco_pos + 12:stco_pos + 16])[0]

                codec = 'unknown'
                if b'hvcC' in moov_data[:10000]:
                    codec = 'hvc1'
                elif b'avcC' in moov_data[:10000]:
                    codec = 'avc1'

                duration = 0
                mvhd_pos = moov_data.find(b'mvhd')
                if mvhd_pos > 0 and mvhd_pos + 20 <= len(moov_data):
                    version = moov_data[mvhd_pos + 4]
                    if version == 0:
                        timescale = struct.unpack('>I', moov_data[mvhd_pos + 12:mvhd_pos + 16])[0]
                        dur = struct.unpack('>I', moov_data[mvhd_pos + 16:mvhd_pos + 20])[0]
                        if timescale > 0:
                            duration = dur / timescale

                total_video_size = 0
                stsz_pos = moov_data.find(b'stsz')
                if stsz_pos > 0 and stsz_pos + 20 <= len(moov_data):
                    sample_size = struct.unpack('>I', moov_data[stsz_pos + 12:stsz_pos + 16])[0]
                    sample_count = struct.unpack('>I', moov_data[stsz_pos + 16:stsz_pos + 20])[0]
                    if sample_size > 0 and sample_count > 0:
                        total_video_size = sample_size * sample_count

                results.append({
                    'disk_offset': disk_off,
                    'moov_size': moov_size,
                    'first_stco': first_stco,
                    'entry_count': entry_count,
                    'codec': codec,
                    'duration': duration,
                    'total_video_size': total_video_size,
                })
            except Exception:
                pass

    log(f'Parsed {len(results)} moov atoms with video info')
    return results


def match_moov_to_files(output_dir, moov_info, disk_path, files_with_moov):
    """Match moov atoms to files that don't have one using NAL validation."""
    all_files = sorted(f for f in os.listdir(output_dir) if f.endswith('.mp4'))
    files_without = [f for f in all_files if f not in files_with_moov]
    log(f'Matching moov to {len(files_without)} files without moov...')

    matched = 0
    used_moovs = set()

    for fn in files_without:
        filepath = os.path.join(output_dir, fn)
        file_size = os.path.getsize(filepath)

        with open(filepath, 'rb') as f:
            file_data = f.read(min(200000, file_size))

        best_match = None
        best_score = 0

        for mi in moov_info:
            stco0 = mi['first_stco']
            if stco0 < 500 or stco0 >= len(file_data) - 8:
                continue

            mi_key = (mi['disk_offset'], mi['moov_size'])
            if mi_key in used_moovs:
                continue

            nal_len = struct.unpack('>I', file_data[stco0:stco0 + 4])[0]
            if nal_len < 100 or nal_len > 10000000:
                continue

            nal_byte = file_data[stco0 + 4]
            score = 0

            if mi['codec'] == 'hvc1':
                nal_type = (nal_byte >> 1) & 0x3F
                if nal_type in (19, 20):  # HEVC IDR
                    score = 100
                elif nal_type in (0, 1):  # HEVC TRAIL
                    score = 80
                else:
                    continue
            elif mi['codec'] == 'avc1':
                nal_type = nal_byte & 0x1F
                if nal_type == 5:  # AVC IDR
                    score = 100
                elif nal_type == 1:  # AVC non-IDR
                    score = 80
                else:
                    continue
            else:
                continue

            # Size consistency bonus
            if mi['total_video_size'] > 0:
                expected = mi['total_video_size'] + mi['moov_size'] + 100000
                ratio = file_size / expected if expected > 0 else 0
                if 0.7 < ratio < 1.3:
                    score += 20

            if score > best_score:
                best_score = score
                best_match = mi

        if best_match and best_score >= 80:
            mi_key = (best_match['disk_offset'], best_match['moov_size'])
            used_moovs.add(mi_key)

            with open(disk_path, 'rb') as fd:
                moov_bytes = aligned_read(fd, best_match['disk_offset'], best_match['moov_size'])

            with open(filepath, 'ab') as of:
                of.write(moov_bytes)

            matched += 1
            log(f'  MATCHED {fn} + moov ({best_match["codec"]}, {best_match["duration"]:.1f}s)')

    log(f'\nMatched {matched} files with moov atoms')
    return matched


def main():
    if len(sys.argv) < 3:
        print(f'Usage: sudo python3 {sys.argv[0]} <disk_device> <output_dir>')
        print(f'Example: sudo python3 {sys.argv[0]} /dev/rdisk4s1 ./recovered/')
        sys.exit(1)

    disk_path = sys.argv[1]
    output_dir = sys.argv[2]
    os.makedirs(output_dir, exist_ok=True)

    start_time = time.time()

    # Step 1: Parse ExFAT boot sector
    log('=' * 60)
    log('Phase 1: Analyzing ExFAT filesystem')
    log('=' * 60)
    params = parse_exfat_boot_sector(disk_path)

    # Step 2: Read FAT table
    log('\n' + '=' * 60)
    log('Phase 2: Reading FAT table')
    log('=' * 60)
    fat_entry, total_entries = read_fat(disk_path, params)

    # Step 3: Find and reconstruct MP4 chains
    log('\n' + '=' * 60)
    log('Phase 3: Recovering files from FAT chains')
    log('=' * 60)
    mp4_chains = find_mp4_chains(disk_path, fat_entry, total_entries, params)
    log(f'Found {len(mp4_chains)} MP4 chains')

    files_with_moov = set()
    for idx, (length, data_size, start, chain) in enumerate(mp4_chains):
        out_fn = f'video_{idx:03d}_{length}clusters_{data_size // 1024 // 1024}MB.mp4'
        out_path = os.path.join(output_dir, out_fn)
        log(f'  Writing {out_fn} ({data_size / 1024 / 1024:.1f}MB)...', end='', flush=True)
        reconstruct_file(disk_path, chain, out_path, params)

        if check_moov_in_file(out_path):
            files_with_moov.add(out_fn)
            log(' [has moov]')
        else:
            log('')

    log(f'\n{len(files_with_moov)} / {len(mp4_chains)} files already have moov')

    # Step 4: Match moov atoms
    log('\n' + '=' * 60)
    log('Phase 4: Matching moov atoms to incomplete files')
    log('=' * 60)
    moov_list = scan_moov_atoms(disk_path, params)
    moov_info = parse_moov_info(disk_path, moov_list)
    match_count = match_moov_to_files(output_dir, moov_info, disk_path, files_with_moov)

    # Summary
    elapsed = time.time() - start_time
    total_playable = len(files_with_moov) + match_count
    total_files = len(mp4_chains)

    log('\n' + '=' * 60)
    log('RECOVERY SUMMARY')
    log('=' * 60)
    log(f'Total files recovered: {total_files}')
    log(f'Files with moov (playable): {total_playable}')
    log(f'Files still missing moov: {total_files - total_playable}')
    log(f'Time elapsed: {elapsed / 60:.1f} minutes')
    log(f'Output directory: {output_dir}')

    # Calculate total size
    total_size = sum(os.path.getsize(os.path.join(output_dir, f))
                     for f in os.listdir(output_dir) if f.endswith('.mp4'))
    log(f'Total data recovered: {total_size / 1024 ** 3:.2f} GB')


if __name__ == '__main__':
    main()
