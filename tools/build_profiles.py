"""Extract and build clean character reference voice profiles from PS1 English audio."""

import os
import wave


def concatenate_wavs(input_paths, output_path, pause_ms=300):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    all_frames = []
    sample_rate = None

    for p in input_paths:
        if not os.path.exists(p):
            print(f"Warning: File {p} not found, skipping.")
            continue
        with wave.open(p, "rb") as wf:
            rate = wf.getframerate()
            if sample_rate is None:
                sample_rate = rate
            frames = wf.readframes(wf.getnframes())
            all_frames.append(frames)
            silence_samples = int(sample_rate * (pause_ms / 1000.0))
            all_frames.append(b"\x00\x00" * silence_samples)

    if not all_frames or sample_rate is None:
        print(f"Failed to create {output_path}")
        return

    with wave.open(output_path, "wb") as out_wf:
        out_wf.setnchannels(1)
        out_wf.setsampwidth(2)
        out_wf.setframerate(sample_rate)
        out_wf.writeframes(b"".join(all_frames))

    with wave.open(output_path, "rb") as out_wf:
        dur = out_wf.getnframes() / out_wf.getframerate()
    print(f"Created profile: {output_path} ({dur:.2f}s)")

def main():
    base = "audio/reference_en"

    # Non-custom character profiles extracted from pristine 2002 PS1 English voice audio

    # 1. Severus Snape / Lucius Malfoy
    snape_lines = [
        f"{base}/line_048_031.wav",
        f"{base}/line_136_050.wav",
        f"{base}/line_142_052.wav",
    ]
    concatenate_wavs(snape_lines, "audio/profiles/snape.wav")

    # 2. Draco Malfoy
    draco_lines = [
        f"{base}/line_115_035.wav",
        f"{base}/line_118_036.wav",
        f"{base}/line_172_062.wav",
    ]
    concatenate_wavs(draco_lines, "audio/profiles/draco.wav")

    # 3. Albus Dumbledore
    dumbledore_lines = [
        f"{base}/line_259_092.wav",
        f"{base}/line_265_094.wav",
        f"{base}/line_385_154.wav",
        f"{base}/line_406_095.wav",
    ]
    concatenate_wavs(dumbledore_lines, "audio/profiles/dumbledore.wav")

    # 4. Tom Riddle
    riddle_lines = [
        f"{base}/line_283_101.wav",
        f"{base}/line_286_150.wav",
        f"{base}/line_307_107.wav",
    ]
    concatenate_wavs(riddle_lines, "audio/profiles/riddle.wav")

    # 5. Rubeus Hagrid
    hagrid_lines = [
        f"{base}/line_301_105.wav",
        f"{base}/line_313_109.wav",
        f"{base}/line_400_079.wav",
    ]
    concatenate_wavs(hagrid_lines, "audio/profiles/hagrid.wav")

    # 6. Mrs. Weasley (Howler)
    mrs_weasley_lines = [
        f"{base}/line_415_005.wav",
    ]
    concatenate_wavs(mrs_weasley_lines, "audio/profiles/mrs_weasley.wav")

    # 7. Sorting Hat
    sorting_hat_lines = [
        f"{base}/line_250_089.wav",
    ]
    concatenate_wavs(sorting_hat_lines, "audio/profiles/sorting_hat.wav")

if __name__ == "__main__":
    main()
