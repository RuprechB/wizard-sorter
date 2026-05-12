import tempfile
import unittest
from pathlib import Path

from wizard_sorter.core import apply_plan, build_plan, search_index, undo_last_apply, write_index


class CoreTests(unittest.TestCase):
    def test_build_plan_apply_and_find(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "inbox"
            dest = base / "sorted"
            root.mkdir()
            (root / "tax-receipt.txt").write_text("tax receipt")
            (root / "photo.jpg").write_bytes(b"image")

            plan = build_plan(root, dest, mode="hybrid", light_scan=True, dedupe=True)
            self.assertEqual(plan["count"], 2)
            self.assertTrue(any("Finance" in row["destination"] for row in plan["plan"]))

            result = apply_plan(plan)
            self.assertEqual(len(result["moved"]), 2)
            self.assertEqual(result["moved"][0]["operation"], "move")
            self.assertFalse(result["errors"])
            write_index(dest, plan, result)
            self.assertTrue(search_index(dest, "tax"))
            undo = undo_last_apply(dest)
            self.assertEqual(len(undo["undone"]), 2)
            self.assertTrue((root / "tax-receipt.txt").exists())

    def test_duplicate_review_is_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "inbox"
            dest = base / "sorted"
            root.mkdir()
            (root / "a.txt").write_text("same")
            (root / "b.txt").write_text("same")

            plan = build_plan(root, dest, mode="hybrid", dedupe=True)
            duplicate_rows = [row for row in plan["plan"] if row["action"] == "duplicate-review"]
            self.assertEqual(len(duplicate_rows), 1)

            result = apply_plan(plan)
            self.assertEqual(len(result["skipped"]), 1)

    def test_copy_mode_and_undo_deletes_copies(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "inbox"
            dest = base / "sorted"
            root.mkdir()
            original = root / "tax-receipt.txt"
            original.write_text("tax receipt")

            plan = build_plan(root, dest, mode="hybrid", dedupe=True)
            result = apply_plan(plan, operation="copy")
            self.assertTrue(original.exists())
            self.assertEqual(result["moved"][0]["operation"], "copy")
            copied = Path(result["moved"][0]["destination"])
            self.assertTrue(copied.exists())
            write_index(dest, plan, result)
            undo_last_apply(dest)
            self.assertTrue(original.exists())
            self.assertFalse(copied.exists())

    def test_duplicate_review_can_move_to_review_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "inbox"
            dest = base / "sorted"
            root.mkdir()
            (root / "a.txt").write_text("same")
            (root / "b.txt").write_text("same")

            plan = build_plan(root, dest, mode="hybrid", dedupe=True)
            result = apply_plan(plan, duplicate_action="move-to-review")
            review_moves = [item for item in result["moved"] if item["duplicate_review"]]
            self.assertEqual(len(review_moves), 1)
            self.assertIn("Duplicate Review", review_moves[0]["destination"])


if __name__ == "__main__":
    unittest.main()
