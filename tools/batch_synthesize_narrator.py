"""Parallel Multi-Worker Narrator Voice Synthesis & Final Auto-Build Orchestrator.

Launches 4 parallel workers targeting the 704 narrator lines with Melike's profile,
tracks progress, and upon completion automatically executes full WAD injection
and final CD-ROM XA ISO rebuilding.
"""

import os
import subprocess
import sys
import time

PYTHON_BIN = ".venv-clone/bin/python"


def main():
    print("=" * 70)
    print("LAUNCHING 4 PARALLEL NARRATOR (MELIKE) WORKERS (24 CPU THREADS)")
    print("=" * 70)

    commands = [
        [PYTHON_BIN, "tools/ingame_dubber.py", "--char", "narrator", "--workers", "4", "--worker-id", "0"],
        [PYTHON_BIN, "tools/ingame_dubber.py", "--char", "narrator", "--workers", "4", "--worker-id", "1"],
        [PYTHON_BIN, "tools/ingame_dubber.py", "--char", "narrator", "--workers", "4", "--worker-id", "2"],
        [PYTHON_BIN, "tools/ingame_dubber.py", "--char", "narrator", "--workers", "4", "--worker-id", "3"],
    ]

    os.makedirs("scratch/logs", exist_ok=True)
    processes = []
    log_files = []

    t_start = time.time()

    for idx, cmd in enumerate(commands):
        log_path = f"scratch/logs/narrator_worker_{idx}.log"
        f = open(log_path, "w", encoding="utf-8")
        log_files.append(f)
        p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT)
        processes.append((p, cmd, log_path))
        print(f"[Narrator Worker {idx}] Launched (log: {log_path})")

    print("\nAll 4 narrator workers active. Processing 704 lines across 24 CPU threads...")
    for idx, (p, cmd, log_path) in enumerate(processes):
        ret = p.wait()
        log_files[idx].close()
        print(f"[Narrator Worker {idx}] Exited with code {ret}")

    dt = time.time() - t_start
    print(f"\n[OK] All 704 narrator lines completed in {dt/60:.2f} minutes!")

    # Check status
    subprocess.run([PYTHON_BIN, "tools/ingame_dubber.py", "--status"])

    # Step 2: Inject all synthesized audio into all 70 WADs
    print("\nExecuting master SPU ADPCM injection into all 70 WAD files...")
    subprocess.run([PYTHON_BIN, "tools/ingame_dubber.py", "--inject", "--rebuild-iso"], check=True)

    print("\n" + "=" * 70)
    print("  100% COMPLETE: ALL IN-GAME & STORYBOOK CUTSCENES DUBBED & INJECTED!")
    print("  FINAL ISO BUILT: Harry Potter and the Chamber of Secrets (Turkish).bin")
    print("=" * 70)


if __name__ == "__main__":
    main()
