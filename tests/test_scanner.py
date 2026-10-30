import os
import tempfile
import unittest
from pathlib import Path

from ecoprune.scanner import scan_folder


class ScannerTests(unittest.TestCase):
    def test_exact_duplicates_and_same_name_different_content(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "same-a.txt").write_bytes(b"identical")
            (root / "same-b.txt").write_bytes(b"identical")
            (root / "left").mkdir()
            (root / "right").mkdir()
            (root / "left" / "note.txt").write_bytes(b"left")
            (root / "right" / "note.txt").write_bytes(b"rite")
            result = scan_folder(root)
            self.assertEqual(len(result.duplicate_groups), 1)
            self.assertEqual({p.path.name for p in result.duplicate_groups[0].files},
                             {"same-a.txt", "same-b.txt"})
            self.assertEqual(result.duplicate_groups[0].recoverable_logical_bytes, 9)
            self.assertEqual(result.files_scanned, 4)
            self.assertEqual(result.logical_bytes, 9 + 9 + 4 + 4)

    def test_read_only_scan_preserves_file_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "one").write_bytes(b"same")
            (root / "two").write_bytes(b"same")
            before = {p: p.read_bytes() for p in root.iterdir()}
            scan_folder(root)
            self.assertEqual(before, {p: p.read_bytes() for p in root.iterdir()})

    def test_hard_link_is_not_counted_as_physical_duplicate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / "original.bin"
            original.write_bytes(b"payload")
            try:
                os.link(original, root / "hardlink.bin")
            except (OSError, NotImplementedError):
                self.skipTest("Hard link creation is unavailable")
            result = scan_folder(root)
            self.assertEqual(result.files_scanned, 1)
            self.assertEqual(result.logical_bytes, 7)
            self.assertEqual(result.skipped_hard_links, 1)
            self.assertEqual(result.duplicate_groups, [])

    def test_symlink_directory_is_not_traversed(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside:
            root, external = Path(temp), Path(outside)
            (external / "secret.txt").write_text("outside", encoding="utf-8")
            try:
                (root / "escape").symlink_to(external, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Directory symlink creation is unavailable")
            result = scan_folder(root)
            self.assertEqual(result.files_scanned, 0)
            self.assertTrue(any("sembolik bağlantı/junction" in issue for issue in result.issues))


if __name__ == "__main__":
    unittest.main()
