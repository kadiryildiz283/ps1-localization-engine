"""Parallel Re-synthesis of Clean In-Game Voice Lines (Dollar-Free).

Runs 4 parallel neural voice synthesis workers across CPU threads:
- Worker 0: Narrator (part 1)
- Worker 1: Narrator (part 2)
- Worker 2: Ron
- Worker 3: Characters (Hagrid, Dumbledore, Draco, Hermione, Snape, Mrs. Weasley)
"""

import os
import subprocess
import sys
import time

PYTHON_BIN = '.venv-clone/bin/python'


def main():
    print('=' * 70)
    print('RE-SYNTHESIZING 120 CLEAN LINES ACROSS 4 PARALLEL WORKERS')
    print('=' * 70)

    commands = [
        # Worker 0: Narrator part 1
        [PYTHON_BIN, 'tools/ingame_dubber.py', '--char', 'narrator', '--workers', '2', '--worker-id', '0'],
        # Worker 1: Narrator part 2
        [PYTHON_BIN, 'tools/ingame_dubber.py', '--char', 'narrator', '--workers', '2', '--worker-id', '1'],
        # Worker 2: Ron
        [PYTHON_BIN, 'tools/ingame_dubber.py', '--char', 'ron'],
        # Worker 3: Other characters
        [PYTHON_BIN, 'tools/ingame_dubber.py', '--char', 'hagrid', 'dumbledore', 'draco', 'hermione', 'snape', 'mrs_weasley'],
    ]

    os.makedirs('scratch/logs', exist_ok=True)
    processes = []
    log_files = []

    t_start = time.time()

    for idx, cmd in enumerate(commands):
        log_path = f'scratch/logs/resynth_worker_{idx}.log'
        f = open(log_path, 'w', encoding='utf-8')
        log_files.append(f)
        p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)
        processes.append((p, cmd, log_path))
        print(f'[Worker {idx}] Launched: {" ".join(cmd[2:])} (log: {log_path})')

    print("\nWaiting for 4 workers to finish...")
    for idx, (p, cmd, log_path) in enumerate(processes):
        ret = p.wait()
        log_files[idx].close()
        print(f"[Worker {idx}] Exited with code {ret}")

    dt = time.time() - t_start
    print(f"\n[OK] All workers finished in {dt/60:.2f} minutes!")

    # Check status
    subprocess.run([PYTHON_BIN, 'tools/ingame_dubber.py', '--status'])


if __name__ == '__main__':
    main()
