#!/usr/bin/env python3
"""
Batch verification of recovered MP4 files using ffmpeg.
Tests each file for playability and reports statistics.

Usage: python3 verify_recovery.py /path/to/recovered/files/
"""

import os, subprocess, sys, re
from concurrent.futures import ThreadPoolExecutor, as_completed


def verify_file(filepath):
    """Test a single file with ffmpeg. Returns (filename, duration, frames, status)."""
    fn = os.path.basename(filepath)
    try:
        result = subprocess.run(
            ['ffmpeg', '-err_detect', 'ignore_err', '-i', filepath, '-f', 'null', '-'],
            capture_output=True, text=True, timeout=300
        )
        output = result.stderr

        # Extract duration
        dur_match = re.search(r'Duration: ([0-9:.]+)', output)
        duration = dur_match.group(1) if dur_match else '?'

        # Extract frame count
        frame_match = re.search(r'frame=\s*(\d+)', output)
        frames = int(frame_match.group(1)) if frame_match else 0

        # Check for errors
        has_errors = 'error_rate' in output
        status = 'ERRORS' if has_errors else 'OK'

        return (fn, duration, frames, status)
    except subprocess.TimeoutExpired:
        return (fn, '?', 0, 'TIMEOUT')
    except Exception as e:
        return (fn, '?', 0, f'FAIL({e})')


def main():
    if len(sys.argv) < 2:
        print(f'Usage: python3 {sys.argv[0]} <recovered_files_dir>')
        sys.exit(1)

    target_dir = sys.argv[1]
    files = sorted(f for f in os.listdir(target_dir) if f.endswith('.mp4'))
    print(f'Verifying {len(files)} files...\n')

    results = []
    ok_count = 0
    error_count = 0
    total_frames = 0

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(verify_file, os.path.join(target_dir, fn)): fn
            for fn in files
        }
        for future in as_completed(futures):
            fn, duration, frames, status = future.result()
            results.append((fn, duration, frames, status))

            marker = 'OK' if status == 'OK' else 'XX'
            print(f'  [{marker}] {duration:>16s} | {frames:>6d} frames | {fn}')

            if status == 'OK':
                ok_count += 1
            else:
                error_count += 1
            total_frames += frames

    # Summary
    total_size = sum(os.path.getsize(os.path.join(target_dir, f)) for f in files)
    print(f'\n{"=" * 60}')
    print(f'RESULTS')
    print(f'{"=" * 60}')
    print(f'Total files: {len(files)}')
    print(f'Playable (OK): {ok_count}')
    print(f'With errors: {error_count}')
    print(f'Total frames: {total_frames}')
    print(f'Total data: {total_size / 1024 ** 3:.2f} GB')


if __name__ == '__main__':
    main()
