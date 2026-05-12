from pathlib import Path

from wizard_sorter.core import build_plan, apply_plan


def test_build_plan_and_apply(tmp_path: Path):
    root = tmp_path / "inbox"
    dest = tmp_path / "sorted"
    root.mkdir()
    (root / "tax-receipt.txt").write_text("tax receipt")
    (root / "photo.jpg").write_bytes(b"image")

    plan = build_plan(root, dest, mode="hybrid", light_scan=True, dedupe=True)
    assert plan["count"] == 2
    assert any("Finance" in row["destination"] for row in plan["plan"])

    result = apply_plan(plan)
    assert len(result["moved"]) == 2
    assert not result["errors"]


def test_duplicate_review_is_skipped(tmp_path: Path):
    root = tmp_path / "inbox"
    dest = tmp_path / "sorted"
    root.mkdir()
    (root / "a.txt").write_text("same")
    (root / "b.txt").write_text("same")

    plan = build_plan(root, dest, mode="hybrid", dedupe=True)
    duplicate_rows = [row for row in plan["plan"] if row["action"] == "duplicate-review"]
    assert len(duplicate_rows) == 1

    result = apply_plan(plan)
    assert len(result["skipped"]) == 1
