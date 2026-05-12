import tempfile
import unittest
from pathlib import Path

from wizard_sorter.core import apply_plan, build_plan, search_index, write_index


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
            self.assertFalse(result["errors"])
            write_index(dest, plan, result)
            self.assertTrue(search_index(dest, "tax"))

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


if __name__ == "__main__":
    unittest.main()
