import tempfile
import unittest
from pathlib import Path

from ecoprune.review import (
    build_preview,
    group_key,
    is_protected_path,
    parse_protected_folders,
)
from ecoprune.scanner import scan_folder


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "docs").mkdir()
        (self.root / "docs-old").mkdir()
        (self.root / "docs" / "copy-a.bin").write_bytes(b"same!")
        (self.root / "docs" / "copy-b.bin").write_bytes(b"same!")
        (self.root / "docs-old" / "copy-c.bin").write_bytes(b"same!")
        self.result = scan_folder(self.root)
        self.group = self.result.duplicate_groups[0]
        self.key = group_key(self.result.root, self.group)

    def tearDown(self):
        self.temp.cleanup()

    def test_protection_uses_path_components_not_text_prefixes(self):
        self.assertTrue(is_protected_path("docs/copy-a.bin", ("docs",)))
        self.assertFalse(is_protected_path("docs-old/copy-c.bin", ("docs",)))
        self.assertTrue(is_protected_path("DOCS/sub/file.bin", ("docs",)))

    def test_candidate_totals_and_reducible_bytes_are_separate(self):
        preview = build_preview(
            self.result,
            {self.key: "docs/copy-a.bin"},
            {(self.key, "docs-old/copy-c.bin")},
            set(),
            ("docs",),
        )
        self.assertTrue(preview.valid, preview.errors)
        self.assertEqual(preview.candidate_logical_bytes, 5)
        self.assertEqual(preview.groups[0].reducible_logical_bytes, 10)
        self.assertEqual(self.result.logical_bytes, 15)
        self.assertEqual(preview.groups[0].candidate_paths, ("docs-old/copy-c.bin",))

    def test_missing_keeper_is_invalid_and_no_candidates_are_selected_by_default(self):
        preview = build_preview(self.result, {}, set(), set())
        self.assertFalse(preview.valid)
        self.assertEqual(preview.candidates, ())
        self.assertEqual(preview.candidate_logical_bytes, 0)

    def test_necessary_group_is_excluded_even_if_old_candidate_choice_remains(self):
        preview = build_preview(
            self.result,
            {self.key: "docs/copy-a.bin"},
            {(self.key, "docs-old/copy-c.bin")},
            {self.key},
        )
        self.assertTrue(preview.valid, preview.errors)
        self.assertTrue(preview.groups[0].necessary)
        self.assertEqual(preview.candidates, ())
        self.assertEqual(preview.candidate_logical_bytes, 0)

    def test_keeper_cannot_be_a_candidate_and_protected_paths_are_rejected(self):
        preview = build_preview(
            self.result,
            {self.key: "docs/copy-a.bin"},
            {
                (self.key, "docs/copy-a.bin"),
                (self.key, "docs/copy-b.bin"),
            },
            set(),
            ("docs",),
        )
        self.assertFalse(preview.valid)
        self.assertTrue(any("korunacak dosya işlem adayı olamaz" in error for error in preview.errors))
        self.assertTrue(any("Korunan klasördeki dosya aday olamaz" in error for error in preview.errors))

    def test_protected_paths_must_be_relative_and_stay_under_root(self):
        self.assertEqual(parse_protected_folders("docs\\important\n./media"),
                         ("docs/important", "media"))
        for invalid in ("../outside", "C:\\private", "\\\\server\\share"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_protected_folders(invalid)


if __name__ == "__main__":
    unittest.main()
