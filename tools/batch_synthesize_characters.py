"""Parallel Multi-Worker Character Voice Synthesis Orchestrator.

Launches 4 parallel workers targeting specific character rosters:
- Worker 0: Harry (Kadir), Draco (Bahadır), Hermione (Cansel)
- Worker 1: Ron (Batuhan) part 1
- Worker 2: Ron (Batuhan) part 2
- Worker 3: Dobby (Efe), Hagrid, Snape, Mrs. Weasley, Riddle, Dumbledore
"""

import os
import subprocess
import time

PYTHON_BIN = ".venv-clone/bin/python"


def main():
    print("=" * 70)
    print("LAUNCHING 4 PARALLEL NEURAL VOICE CLONING WORKERS (24 CPU THREADS)")
    print("=" * 70)

    commands = [
        # Worker 0: Ron, Harry, Draco (77 missing lines)
        [PYTHON_BIN, "tools/deterministic_audio_injector.py", "--synthesize", "--char", "ron", "harry", "draco"],
        # Worker 1: Mrs. Weasley, Dumbledore (85 missing lines)
        [PYTHON_BIN, "tools/deterministic_audio_injector.py", "--synthesize", "--char", "mrs_weasley", "dumbledore"],
        # Worker 2: Snape, Hermione, Hagrid (77 missing lines)
        [PYTHON_BIN, "tools/deterministic_audio_injector.py", "--synthesize", "--char", "snape", "hermione", "hagrid"],
        # Worker 3: Narrator, Riddle, Dobby (34 missing lines)
        [PYTHON_BIN, "tools/deterministic_audio_injector.py", "--synthesize", "--char", "narrator", "riddle", "dobby"],
    ]

    os.makedirs("scratch/logs", exist_ok=True)
    processes = []
    log_files = []

    t_start = time.time()

    for idx, cmd in enumerate(commands):
        log_path = f"scratch/logs/worker_{idx}.log"
        f = open(log_path, "w", encoding="utf-8")
        log_files.append(f)
        p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)
        processes.append((p, cmd, log_path))
        print(f"[Worker {idx}] Launched: {' '.join(cmd[2:])} (log: {log_path})")

    # Wait for all processes to complete
    print("\nAll workers active in background. Monitoring completion...")
    for idx, (p, cmd, log_path) in enumerate(processes):
        ret = p.wait()
        log_files[idx].close()
        print(f"[Worker {idx}] Exited with code {ret}")

    dt = time.time() - t_start
    print(f"\n[OK] All 4 character synthesis workers completed in {dt/60:.2f} minutes!")

    # Print final status
    subprocess.run([PYTHON_BIN, "tools/deterministic_audio_injector.py", "--status"])


if __name__ == "__main__":
    main()
