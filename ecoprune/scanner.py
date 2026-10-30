"""Read-only, streaming duplicate scan engine for EcoPrune."""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

CHUNK_SIZE = 1024 * 1024
_REPARSE_POINT = 0x400  # Windows junctions and other reparse points


@dataclass(frozen=True)
class ScannedFile:
    path: Path
    size: int
    sha256: str


@dataclass(frozen=True)
class DuplicateGroup:
    files: tuple[ScannedFile, ...]
    recoverable_logical_bytes: int


@dataclass
class ScanResult:
    root: Path
    files_scanned: int = 0
    logical_bytes: int = 0
    duplicate_groups: list[DuplicateGroup] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    skipped_hard_links: int = 0


class FileChangedError(OSError):
    """Raised if a file's identity or metadata changes during a scan operation."""


def _is_reparse_point(info: os.stat_result) -> bool:
    return bool(getattr(info, "st_file_attributes", 0) & _REPARSE_POINT)


def _signature(info: os.stat_result) -> tuple[int, int, int, int]:
    # Windows may update st_ctime as a side effect of opening/reading a file.
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def _contained(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=True).relative_to(root)
        return True
    except (OSError, ValueError, RuntimeError):
        return False


def _walk(root: Path, result: ScanResult) -> Iterator[Path]:
    """Yield regular files without traversing symlinks or junctions."""
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    path = Path(entry.path)
                    try:
                        info = entry.stat(follow_symlinks=False)
                        if entry.is_symlink() or _is_reparse_point(info):
                            result.issues.append(f"Atlandı (sembolik bağlantı/junction): {path}")
                            continue
                        if stat.S_ISDIR(info.st_mode):
                            if _contained(path, root):
                                stack.append(path)
                            else:
                                result.issues.append(f"Atlandı (seçilen klasörün dışında): {path}")
                        elif stat.S_ISREG(info.st_mode):
                            if _contained(path, root):
                                yield path
                            else:
                                result.issues.append(f"Atlandı (seçilen klasörün dışında): {path}")
                    except OSError as exc:
                        result.issues.append(f"Okunamadı: {path} ({exc})")
        except OSError as exc:
            result.issues.append(f"Klasör okunamadı: {directory} ({exc})")


def _check_readable(path: Path, root: Path) -> tuple[int, tuple[int, int, int, int]]:
    """Check access and metadata for all files; hash only same-size candidates."""
    if not _contained(path, root):
        raise OSError("Dosya seçilen klasörün dışına yönelmiş")
    before = path.lstat()
    if stat.S_ISLNK(before.st_mode) or _is_reparse_point(before):
        raise OSError("Dosya sembolik bağlantı/junction haline gelmiş")
    if not stat.S_ISREG(before.st_mode):
        raise OSError("Dosya normal dosya olmaktan çıkmış")
    with path.open("rb") as stream:
        if _signature(os.fstat(stream.fileno())) != _signature(before):
            raise FileChangedError("Dosya açılırken değişmiş")
    if _signature(path.lstat()) != _signature(before):
        raise FileChangedError("Tarama sırasında dosya değişmiş")
    return before.st_size, _signature(before)


def _hash_file(path: Path, root: Path) -> tuple[str, int, tuple[int, int, int, int]]:
    if not _contained(path, root):
        raise OSError("Dosya seçilen klasörün dışına yönelmiş")
    before = path.lstat()
    if stat.S_ISLNK(before.st_mode) or _is_reparse_point(before):
        raise OSError("Dosya sembolik bağlantı/junction haline gelmiş")
    if not stat.S_ISREG(before.st_mode):
        raise OSError("Dosya normal dosya olmaktan çıkmış")
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as stream:
        if _signature(os.fstat(stream.fileno())) != _signature(before):
            raise FileChangedError("Dosya açılırken değişmiş")
        while True:
            block = stream.read(CHUNK_SIZE)
            if not block:
                break
            digest.update(block)
            count += len(block)
        after_open = os.fstat(stream.fileno())
    if (_signature(before) != _signature(after_open)
            or _signature(before) != _signature(path.lstat())
            or count != before.st_size):
        raise FileChangedError("Tarama sırasında dosya değişmiş")
    return digest.hexdigest(), count, _signature(before)


def _files_equal(left: ScannedFile, right: ScannedFile, root: Path) -> bool:
    """Compare bytes in bounded chunks, checking that neither path changed."""
    for file in (left, right):
        if not _contained(file.path, root):
            raise OSError("Dosya seçilen klasörün dışına yönelmiş")
    before_left, before_right = left.path.lstat(), right.path.lstat()
    if any(stat.S_ISLNK(info.st_mode) or _is_reparse_point(info)
           for info in (before_left, before_right)):
        raise OSError("Dosyalardan biri sembolik bağlantı/junction haline gelmiş")
    if before_left.st_size != before_right.st_size:
        return False
    with left.path.open("rb") as a, right.path.open("rb") as b:
        if _signature(os.fstat(a.fileno())) != _signature(before_left):
            raise FileChangedError("Dosya içerik doğrulaması sırasında değişmiş")
        if _signature(os.fstat(b.fileno())) != _signature(before_right):
            raise FileChangedError("Dosya içerik doğrulaması sırasında değişmiş")
        equal = True
        while True:
            block_a, block_b = a.read(CHUNK_SIZE), b.read(CHUNK_SIZE)
            if block_a != block_b:
                equal = False
                break
            if not block_a:
                break
        after_a, after_b = os.fstat(a.fileno()), os.fstat(b.fileno())
    if (_signature(before_left) != _signature(after_a)
            or _signature(before_right) != _signature(after_b)
            or _signature(before_left) != _signature(left.path.lstat())
            or _signature(before_right) != _signature(right.path.lstat())):
        raise FileChangedError("İçerik doğrulanırken dosya değişmiş")
    return equal


def scan_folder(folder: str | os.PathLike[str]) -> ScanResult:
    """Scan read-only: size filter, SHA-256 candidates, then exact byte checks."""
    supplied = Path(folder).expanduser()
    root = supplied.resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(str(root))
    result = ScanResult(root=root)
    by_identity: dict[tuple[int, int], Path] = {}
    by_size: dict[int, list[Path]] = {}
    file_sizes: dict[Path, int] = {}
    invalid_paths: set[Path] = set()

    # First pass: enumerate, deduplicate physical identities and bucket by size.
    for path in _walk(root, result):
        try:
            initial = path.lstat()
            if not _contained(path, root):
                raise OSError("Seçilen klasörün dışına yönelmiş")
            identity = (initial.st_dev, initial.st_ino)
            if initial.st_ino and identity in by_identity:
                result.skipped_hard_links += 1
                continue
            size, _ = _check_readable(path, root)
            if initial.st_ino:
                by_identity[identity] = path
            file_sizes[path] = size
            by_size.setdefault(size, []).append(path)
        except FileChangedError as exc:
            invalid_paths.add(path)
            result.issues.append(f"Tarama sırasında değişti: {path} ({exc})")
        except OSError as exc:
            invalid_paths.add(path)
            result.issues.append(f"Okunamadı veya atlandı: {path} ({exc})")

    # Second pass: hash only files that have at least one same-size peer.
    candidates: dict[tuple[int, str], list[ScannedFile]] = {}
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        for path in paths:
            try:
                digest, actual_size, _ = _hash_file(path, root)
                candidates.setdefault((actual_size, digest), []).append(
                    ScannedFile(path, actual_size, digest)
                )
            except FileChangedError as exc:
                invalid_paths.add(path)
                result.issues.append(f"Tarama sırasında değişti: {path} ({exc})")
            except OSError as exc:
                invalid_paths.add(path)
                result.issues.append(f"Doğrulanamadı: {path} ({exc})")

    # Final pass: SHA-256 narrows candidates, streamed byte comparison confirms.
    for group in candidates.values():
        if len(group) < 2:
            continue
        confirmed = [group[0]]
        for candidate in group[1:]:
            try:
                if _files_equal(group[0], candidate, root):
                    confirmed.append(candidate)
            except FileChangedError as exc:
                invalid_paths.update((group[0].path, candidate.path))
                result.issues.append(f"Tarama sırasında değişti: {candidate.path} ({exc})")
            except OSError as exc:
                invalid_paths.update((group[0].path, candidate.path))
                result.issues.append(f"Doğrulanamadı: {candidate.path} ({exc})")
        if len(confirmed) > 1:
            result.duplicate_groups.append(DuplicateGroup(
                files=tuple(confirmed),
                recoverable_logical_bytes=(len(confirmed) - 1) * confirmed[0].size,
            ))

    result.files_scanned = sum(1 for path in file_sizes if path not in invalid_paths)
    result.logical_bytes = sum(size for path, size in file_sizes.items() if path not in invalid_paths)
    result.duplicate_groups = [
        group for group in result.duplicate_groups
        if all(file.path not in invalid_paths for file in group.files)
    ]
    return result
