import os
import unittest
import wave

from tools.dirdat import DirDatArchive
from tools.iso_fs import Ps1IsoReader


class TestBurrowDubbing(unittest.TestCase):
    def setUp(self):
        self.wad_path = "extracted/T1L2M001.WAD"
        self.iso_path = "Harry Potter and the Chamber of Secrets (Turkish).bin"
        
    def test_all_17_clean_audio_files_exist_and_conforming(self):
        expected_files = [
            ("audio/burrow_clean/cue_02_ron.wav", 4.063),
            ("audio/burrow_clean/cue_05_ron.wav", 2.601),
            ("audio/burrow_clean/cue_08_ron.wav", 4.714),
            ("audio/burrow_clean/cue_11_ron.wav", 6.989),
            ("audio/burrow_clean/cue_14_ron.wav", 9.102),
            ("audio/burrow_clean/cue_17_ron.wav", 5.689),
            ("audio/burrow_clean/cue_20_mrs_weasley.wav", 10.890),
            ("audio/burrow_clean/cue_23_ron.wav", 7.477),
            ("audio/burrow_clean/cue_26_ron.wav", 6.014),
            ("audio/burrow_clean/cue_29_ron.wav", 8.127),
            ("audio/burrow_clean/cue_32_ron.wav", 1.788),
            ("audio/burrow_clean/cue_35_ron.wav", 2.763),
            ("audio/burrow_clean/cue_39_ron.wav", 4.551),
            ("audio/burrow_clean/cue_42_ron.wav", 9.102),
            ("audio/burrow_clean/cue_45_ron.wav", 3.576),
            ("audio/burrow_clean/cue_49_harry.wav", 2.113),
            ("audio/burrow_clean/cue_52_ron.wav", 2.438),
        ]
        self.assertEqual(len(expected_files), 17)
        for fpath, max_dur in expected_files:
            self.assertTrue(os.path.exists(fpath), f"File {fpath} not found")
            with wave.open(fpath, "rb") as wf:
                self.assertEqual(wf.getframerate(), 22050)
                self.assertEqual(wf.getnchannels(), 1)
                dur = wf.getnframes() / float(wf.getframerate())
                self.assertLessEqual(dur, max_dur + 0.05, f"{fpath} exceeds duration budget: {dur} > {max_dur}")

    def test_injected_wad_integrity(self):
        self.assertTrue(os.path.exists(self.wad_path))
        with open(self.wad_path, "rb") as f:
            wad = f.read()
            
        self.assertEqual(len(wad), 8491008)
        dne_pos = wad.find(b" DNE")
        self.assertNotEqual(dne_pos, -1)
        audio_base = (dne_pos + 2047) // 2048 * 2048
        
        # Check all 17 primary cues have audio and 0x01 terminal flag
        primary_cues = [
            (2,  0x04F000, 51200),
            (5,  0x06C000, 32768),
            (8,  0x07E800, 59392),
            (11, 0x0A6000, 88064),
            (14, 0x0D9800, 114688),
            (17, 0x119000, 71680),
            (20, 0x140000, 137216),
            (23, 0x187800, 94208),
            (26, 0x1BC000, 75776),
            (29, 0x1ED800, 102400),
            (32, 0x222800, 22528),
            (35, 0x22F000, 34816),
            (39, 0x300800, 57344),
            (42, 0x324800, 114688),
            (45, 0x36A000, 45056),
            (49, 0x664800, 26624),
            (52, 0x670800, 30720),
        ]
        self.assertEqual(len(primary_cues), 17)
        for cue_idx, a_off, sz in primary_cues:
            cue_bytes = wad[audio_base + a_off : audio_base + a_off + sz]
            self.assertEqual(len(cue_bytes), sz)
            self.assertEqual(cue_bytes[-15], 0x01, f"Cue {cue_idx} missing 0x01 mute terminal")
            non_zero = sum(1 for b in cue_bytes if b != 0)
            self.assertGreater(non_zero, 1000, f"Cue {cue_idx} appears empty: non_zero={non_zero}")

        # Check foreign slots are muted
        foreign_cues = [
            (3,  0x05B800, 26624),
            (4,  0x062000, 40960),
            (15, 0x0F5800, 67584),
            (16, 0x106000, 77824),
            (18, 0x12A800, 38912),
            (19, 0x134000, 49152),
        ]
        for cue_idx, a_off, sz in foreign_cues:
            cue_bytes = wad[audio_base + a_off : audio_base + a_off + sz]
            non_zero = sum(1 for b in cue_bytes if b not in (0x00, 0x01))
            self.assertEqual(non_zero, 0, f"Foreign slot {cue_idx} contains audio: {non_zero}")
            self.assertEqual(cue_bytes[-15], 0x01)

    def test_disc_byte_exact_match(self):
        self.assertTrue(os.path.exists(self.iso_path))
        with open(self.wad_path, "rb") as f:
            local_wad = f.read()
            
        with Ps1IsoReader(self.iso_path) as iso:
            archive = DirDatArchive.from_iso(iso)
            self.assertIn("T1L2M001.WAD", archive.entry_map)
            entry = archive.entry_map["T1L2M001.WAD"]
            iso_wad = iso.read_file_bytes("POTTER.DAT", entry.offset, entry.size)
            
        self.assertEqual(len(local_wad), len(iso_wad))
        self.assertEqual(local_wad, iso_wad)

if __name__ == "__main__":
    unittest.main()
