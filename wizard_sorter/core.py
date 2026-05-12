from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

EXCLUDED_DIRS = {".git", "node_modules", ".next", "__pycache__", ".venv", "venv", ".wizard-sorter"}
LIGHT_SCAN_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".py", ".js", ".ts", ".tsx", ".html", ".css"}

TYPE_BUCKETS = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".svg"},
    "Videos": {".mp4", ".mov", ".mkv", ".avi", ".webm"},
    "Audio": {".mp3", ".wav", ".m4a", ".flac", ".aac"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".md"},
    "Spreadsheets": {".xls", ".xlsx", ".csv", ".tsv", ".numbers"},
    "Presentations": {".ppt", ".pptx", ".key"},
    "Archives": {".zip", ".tar", ".gz", ".rar", ".7z"},
    "Code": {".js", ".ts", ".tsx", ".jsx", ".py", ".rb", ".go", ".rs", ".java", ".html", ".css", ".json", ".yaml", ".yml"},
}

LIFE_RULES = {
    "Finance": ["invoice", "receipt", "tax", "bank", "statement", "paystub", "budget", "accounting"],
    "Work": ["resume", "contract", "client", "proposal", "meeting", "okr", "quarterly"],
    "Health": ["medical", "health", "doctor", "dental", "prescription", "clinic"],
    "Home": ["home", "lease", "mortgage", "utility", "insurance", "landlord"],
    "Projects": ["project", "spec", "roadmap", "design", "build", "todo"],
}

@dataclass
class FileRecord:
    path: str
    name: str
    extension: str
    size: int
    modified_at: str
    type_bucket: str
    life_area: str
    sha256: Optional[str] = None
    light_text: Optional[str] = None

@dataclass
class PlanRow:
    source: str
    destination: str
    action: str
    confidence: float
    reason: str
    warnings: List[str]
    duplicate_of: Optional[str] = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_parts(path: Path) -> bool:
    return not any(part in EXCLUDED_DIRS for part in path.parts)


def type_bucket(path: Path) -> str:
    suffix = path.suffix.lower()
    for bucket, extensions in TYPE_BUCKETS.items():
        if suffix in extensions:
            return bucket
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed:
        return guessed.split("/", 1)[0].title()
    return "Other"


def read_light_text(path: Path, limit: int = 8192) -> Optional[str]:
    if path.suffix.lower() not in LIGHT_SCAN_EXTENSIONS:
        return None
    try:
        return path.read_text(errors="ignore")[:limit]
    except OSError:
        return None


def infer_life_area(path: Path, light_text: Optional[str] = None) -> str:
    haystack = f"{path.name} {light_text or ''}".lower()
    for area, keywords in LIFE_RULES.items():
        if any(re.search(rf"\b{re.escape(keyword)}\b", haystack) for keyword in keywords):
            return area
    return "Inbox"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if safe_parts(path) and path.is_file():
            yield path


def inventory(root: Path, *, light_scan: bool = False, hash_files: bool = False) -> List[FileRecord]:
    records: List[FileRecord] = []
    for path in iter_files(root):
        text = read_light_text(path) if light_scan else None
        stat = path.stat()
        records.append(FileRecord(
            path=str(path),
            name=path.name,
            extension=path.suffix.lower(),
            size=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            type_bucket=type_bucket(path),
            life_area=infer_life_area(path, text),
            sha256=sha256(path) if hash_files else None,
            light_text=text,
        ))
    return records


def destination_parts(record: FileRecord, mode: str) -> List[str]:
    dt = datetime.fromisoformat(record.modified_at)
    if mode == "file-type":
        return [record.type_bucket]
    if mode == "date":
        return [str(dt.year), f"{dt.month:02d}"]
    if mode == "life-area":
        return [record.life_area]
    if mode == "action-state":
        return ["Needs Review"]
    return [record.life_area, record.type_bucket]


def unique_destination(dest: Path) -> Tuple[Path, List[str]]:
    warnings: List[str] = []
    if not dest.exists():
        return dest, warnings
    warnings.append("destination exists; proposed unique filename")
    stem, suffix = dest.stem, dest.suffix
    for i in range(2, 10_000):
        candidate = dest.with_name(f"{stem} ({i}){suffix}")
        if not candidate.exists():
            return candidate, warnings
    raise RuntimeError(f"could not find unique destination for {dest}")


def build_plan(root: Path, dest_root: Path, *, mode: str = "hybrid", light_scan: bool = False, dedupe: bool = False) -> dict:
    records = inventory(root, light_scan=light_scan, hash_files=dedupe)
    first_by_hash: Dict[str, FileRecord] = {}
    rows: List[PlanRow] = []
    for record in records:
        src = Path(record.path)
        duplicate_of = None
        action = "move"
        warnings: List[str] = []
        if dedupe and record.sha256:
            previous = first_by_hash.get(record.sha256)
            if previous:
                duplicate_of = previous.path
                action = "duplicate-review"
                warnings.append("same sha256 as another file; do not delete automatically")
            else:
                first_by_hash[record.sha256] = record
        proposed = dest_root.joinpath(*destination_parts(record, mode), record.name)
        proposed, unique_warnings = unique_destination(proposed)
        warnings.extend(unique_warnings)
        confidence = 0.62 if mode == "hybrid" else 0.72
        if record.life_area == "Inbox":
            confidence -= 0.18
        rows.append(PlanRow(
            source=record.path,
            destination=str(proposed),
            action=action,
            confidence=round(max(confidence, 0.1), 2),
            reason=f"mode={mode}; life_area={record.life_area}; type={record.type_bucket}",
            warnings=warnings,
            duplicate_of=duplicate_of,
        ))
    return {
        "version": 1,
        "created_at": now_iso(),
        "root": str(root),
        "destination_root": str(dest_root),
        "mode": mode,
        "light_scan": light_scan,
        "dedupe": dedupe,
        "count": len(rows),
        "plan": [asdict(row) for row in rows],
    }


def apply_plan(plan: dict, *, allow_duplicate_review: bool = False) -> dict:
    moved, skipped, errors = [], [], []
    for row in plan.get("plan", []):
        action = row.get("action")
        if action == "duplicate-review" and not allow_duplicate_review:
            skipped.append({"source": row.get("source"), "reason": "duplicate-review requires manual decision"})
            continue
        if action not in {"move", "duplicate-review"}:
            skipped.append({"source": row.get("source"), "reason": f"unsupported action {action}"})
            continue
        src = Path(row["source"])
        dest = Path(row["destination"])
        try:
            if not src.exists():
                skipped.append({"source": str(src), "reason": "source missing"})
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            final_dest, _ = unique_destination(dest)
            shutil.move(str(src), str(final_dest))
            moved.append({"source": str(src), "destination": str(final_dest)})
        except OSError as exc:
            errors.append({"source": str(src), "destination": str(dest), "error": str(exc)})
    return {"moved": moved, "skipped": skipped, "errors": errors}


def write_index(dest_root: Path, plan: dict, apply_result: Optional[dict] = None) -> Path:
    state_dir = dest_root / ".wizard-sorter"
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "index.json"
    file_locations = []
    for row in plan.get("plan", []):
        applied = next((item for item in (apply_result or {}).get("moved", []) if item.get("source") == row.get("source")), None)
        file_locations.append({
            "name": Path(applied["destination"] if applied else row.get("destination", "")).name,
            "source": row.get("source"),
            "destination": applied["destination"] if applied else row.get("destination"),
            "action": row.get("action"),
            "reason": row.get("reason"),
            "duplicate_of": row.get("duplicate_of"),
        })
    payload = {"updated_at": now_iso(), "file_locations": file_locations, "plan": plan, "last_apply": apply_result}
    path.write_text(json.dumps(payload, indent=2))
    return path


def search_index(dest_root: Path, query: str, *, limit: int = 10) -> List[dict]:
    path = dest_root / ".wizard-sorter" / "index.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    terms = [term.lower() for term in re.findall(r"[\w.-]+", query)]
    scored = []
    for item in data.get("file_locations", []):
        haystack = " ".join(str(item.get(key) or "") for key in ["name", "source", "destination", "reason"]).lower()
        score = sum(1 for term in terms if term in haystack)
        if score:
            scored.append({**item, "score": score})
    scored.sort(key=lambda item: (-item["score"], item.get("name", "")))
    return scored[:limit]


def fallback_find(root: Path, query: str, *, limit: int = 10) -> List[dict]:
    terms = [term.lower() for term in re.findall(r"[\w.-]+", query)]
    results = []
    for path in iter_files(root):
        haystack = str(path).lower()
        score = sum(1 for term in terms if term in haystack)
        if score:
            stat = path.stat()
            results.append({
                "name": path.name,
                "destination": str(path),
                "score": score,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                "reason": "fallback path/name search",
            })
    results.sort(key=lambda item: (-item["score"], item.get("name", "")))
    return results[:limit]
