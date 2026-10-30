"""Pure selection and size rules for reviewing duplicate groups."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import PureWindowsPath
from typing import Mapping, Sequence

from .scanner import DuplicateGroup, ScanResult, ScannedFile


@dataclass(frozen=True)
class ReviewFile:
    relative_path: str
    size: int
    protected: bool


@dataclass(frozen=True)
class GroupPreview:
    key: str
    files: tuple[ReviewFile, ...]
    keeper_path: str | None
    candidate_paths: tuple[str, ...]
    necessary: bool
    reducible_logical_bytes: int


@dataclass(frozen=True)
class SelectedCandidate:
    group_key: str
    relative_path: str
    size: int


@dataclass(frozen=True)
class SelectionPreview:
    groups: tuple[GroupPreview, ...]
    candidates: tuple[SelectedCandidate, ...]
    candidate_logical_bytes: int
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


def relative_file_path(root, file: ScannedFile) -> str:
    """Return a display-safe path relative to the scanned root."""
    return file.path.relative_to(root).as_posix()


def group_key(root, group: DuplicateGroup) -> str:
    paths = sorted(relative_file_path(root, file).casefold() for file in group.files)
    raw = "\0".join(paths).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]


def parse_protected_folders(value: str) -> tuple[str, ...]:
    """Parse root-relative folder paths and reject absolute or escaping paths."""
    parsed: list[str] = []
    seen: set[tuple[str, ...]] = set()
    for line_number, raw in enumerate(value.splitlines(), start=1):
        raw = raw.strip()
        if not raw:
            continue
        path = PureWindowsPath(raw)
        parts = path.parts
        if path.is_absolute() or path.drive or any(part == ".." for part in parts):
            raise ValueError(f"{line_number}. satır köke göreli ve kök içinde olmalı: {raw}")
        if not parts:
            raise ValueError(f"{line_number}. satırda geçerli klasör yolu yok.")
        canonical_parts = tuple(part for part in parts if part not in (".", "\\"))
        if not canonical_parts:
            raise ValueError(f"{line_number}. satırda geçerli klasör yolu yok.")
        key = tuple(part.casefold() for part in canonical_parts)
        if key not in seen:
            seen.add(key)
            parsed.append("/".join(canonical_parts))
    return tuple(parsed)


def is_protected_path(relative_path: str, protected_folders: Sequence[str]) -> bool:
    """Use path components for containment; e.g. 'docs' does not match 'docs-old'."""
    file_parts = tuple(part.casefold() for part in PureWindowsPath(relative_path).parts)
    for folder in protected_folders:
        folder_parts = tuple(part.casefold() for part in PureWindowsPath(folder).parts)
        if folder_parts and file_parts[:len(folder_parts)] == folder_parts:
            return True
    return False


def build_preview(
    result: ScanResult,
    keepers: Mapping[str, str],
    selected_candidates: set[tuple[str, str]],
    necessary_groups: set[str],
    protected_folders: Sequence[str] = (),
) -> SelectionPreview:
    """Validate all selections and calculate candidate logical bytes."""
    errors: list[str] = []
    previews: list[GroupPreview] = []
    candidates: list[SelectedCandidate] = []
    recognized_candidate_keys: set[tuple[str, str]] = set()

    for group in result.duplicate_groups:
        key = group_key(result.root, group)
        group_files = tuple(
            ReviewFile(
                relative_path=relative_file_path(result.root, file),
                size=file.size,
                protected=is_protected_path(relative_file_path(result.root, file), protected_folders),
            )
            for file in group.files
        )
        by_path = {file.relative_path: file for file in group_files}
        keeper = keepers.get(key)
        if keeper not in by_path:
            errors.append(f"Grup {key}: korunacak dosyayı seçin.")
            keeper = None

        necessary = key in necessary_groups
        selected_paths: list[str] = []
        for path, file in by_path.items():
            candidate_key = (key, path)
            if candidate_key not in selected_candidates:
                continue
            recognized_candidate_keys.add(candidate_key)
            if necessary:
                continue
            if keeper is None:
                continue
            if path == keeper:
                errors.append(f"Grup {key}: korunacak dosya işlem adayı olamaz.")
            elif file.protected:
                errors.append(f"Korunan klasördeki dosya aday olamaz: {path}")
            else:
                selected_paths.append(path)
                candidates.append(SelectedCandidate(key, path, file.size))

        previews.append(GroupPreview(
            key=key,
            files=group_files,
            keeper_path=keeper,
            candidate_paths=tuple(selected_paths),
            necessary=necessary,
            reducible_logical_bytes=group.recoverable_logical_bytes,
        ))

    unknown = selected_candidates - recognized_candidate_keys
    if unknown:
        errors.append("Seçimde bu taramadaki bir gruba ait olmayan dosya kaldı; önizlemeyi yenileyin.")
    return SelectionPreview(
        groups=tuple(previews),
        candidates=tuple(candidates),
        candidate_logical_bytes=sum(candidate.size for candidate in candidates),
        errors=tuple(errors),
    )
