"""Managed PNG/JPEG/BMP import pipeline for appearance themes."""

from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

from PIL import Image, ImageCms, ImageOps


MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_DECODED_PIXELS = 64 * 1024 * 1024
SUPPORTED_SOURCE_FORMATS = frozenset({"PNG", "JPEG", "BMP"})
_MANAGED_FILENAME_RE = re.compile(
    r"^(?P<uuid>[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})\.png$"
)


class ThemeAssetError(Exception):
    pass


class UnsupportedThemeImageError(ThemeAssetError, ValueError):
    pass


class ThemeImageLimitError(ThemeAssetError, ValueError):
    pass


class InvalidManagedAssetPath(ThemeAssetError, ValueError):
    pass


class AssetInUseError(ThemeAssetError, PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class ManagedThemeAsset:
    relative_path: str
    content_hash: str
    width: int
    height: int
    file_size: int


def _canonical_uuid4_filename(filename: str) -> bool:
    match = _MANAGED_FILENAME_RE.fullmatch(filename)
    if not match:
        return False
    try:
        parsed = uuid.UUID(match.group("uuid"))
    except ValueError:
        return False
    return parsed.version == 4 and str(parsed) == match.group("uuid")


class ThemeAssetStore:
    """Normalize external images before a theme-state transaction references them."""

    def __init__(
        self,
        theme_root: str | os.PathLike[str] | None = None,
        *,
        max_source_bytes: int = MAX_SOURCE_BYTES,
        max_decoded_pixels: int = MAX_DECODED_PIXELS,
    ):
        if theme_root is None:
            from misc_func import get_app_base_path

            root = Path(get_app_base_path()) / "data" / "themes"
        else:
            supplied = Path(theme_root)
            root = supplied.parent if supplied.name.lower() == "assets" else supplied
        if max_source_bytes <= 0 or max_decoded_pixels <= 0:
            raise ValueError("image limits must be positive")
        self.root = root
        self.assets_path = root / "assets"
        self.max_source_bytes = int(max_source_bytes)
        self.max_decoded_pixels = int(max_decoded_pixels)

    def import_asset(self, source_path: str | os.PathLike[str]) -> ManagedThemeAsset:
        source = Path(source_path)
        if not source.is_file():
            raise FileNotFoundError(source)
        self.root.mkdir(parents=True, exist_ok=True)
        self.assets_path.mkdir(parents=True, exist_ok=True)

        copied_fd: int | None = None
        copied_path: str | None = None
        output_fd: int | None = None
        output_path: str | None = None
        try:
            # Deliberately copy first: validation and decoding never race a
            # caller replacing or truncating the source file.
            copied_fd, copied_path = tempfile.mkstemp(
                prefix=".theme-import-", suffix=source.suffix, dir=self.root
            )
            os.close(copied_fd)
            copied_fd = None
            shutil.copyfile(source, copied_path)
            copied = Path(copied_path)
            size = copied.stat().st_size
            if size > self.max_source_bytes:
                raise ThemeImageLimitError(
                    f"theme image exceeds {self.max_source_bytes} byte source limit"
                )

            normalized, destination_icc = self._decode_and_normalize(copied)
            asset_id = str(uuid.uuid4())
            final_path = self.assets_path / f"{asset_id}.png"
            output_fd, output_path = tempfile.mkstemp(
                prefix=f".{asset_id}.", suffix=".tmp", dir=self.assets_path
            )
            with os.fdopen(output_fd, "w+b") as handle:
                output_fd = None
                save_options = {"format": "PNG"}
                if destination_icc:
                    save_options["icc_profile"] = destination_icc
                normalized.save(handle, **save_options)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(output_path, final_path)
            output_path = None

            digest = hashlib.sha256()
            with final_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            return ManagedThemeAsset(
                relative_path=f"assets/{final_path.name}",
                content_hash=digest.hexdigest(),
                width=normalized.width,
                height=normalized.height,
                file_size=final_path.stat().st_size,
            )
        finally:
            if copied_fd is not None:
                os.close(copied_fd)
            if output_fd is not None:
                os.close(output_fd)
            for temporary in (copied_path, output_path):
                if temporary and os.path.exists(temporary):
                    try:
                        os.remove(temporary)
                    except OSError:
                        pass

    def _decode_and_normalize(self, copied_path: Path) -> tuple[Image.Image, bytes | None]:
        try:
            with Image.open(copied_path) as opened:
                source_format = (opened.format or "").upper()
                if source_format not in SUPPORTED_SOURCE_FORMATS:
                    raise UnsupportedThemeImageError(
                        f"unsupported theme image format: {source_format or 'unknown'}"
                    )
                width, height = opened.size
                if width <= 0 or height <= 0 or width * height > self.max_decoded_pixels:
                    raise ThemeImageLimitError(
                        f"decoded theme image exceeds {self.max_decoded_pixels} pixel limit"
                    )
                opened.seek(0)
                opened.load()
                image = ImageOps.exif_transpose(opened)
                icc_bytes = opened.info.get("icc_profile")
                image, destination_icc = self._convert_to_srgb_when_possible(image, icc_bytes)
                return image.convert("RGBA"), destination_icc
        except (UnsupportedThemeImageError, ThemeImageLimitError):
            raise
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            raise UnsupportedThemeImageError(f"cannot decode theme image: {exc}") from exc

    @staticmethod
    def _convert_to_srgb_when_possible(
        image: Image.Image, icc_bytes: bytes | None
    ) -> tuple[Image.Image, bytes | None]:
        if not icc_bytes:
            return image, None
        try:
            source_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_bytes))
            destination_profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
            alpha = image.getchannel("A") if "A" in image.getbands() else None
            converted = ImageCms.profileToProfile(
                image.convert("RGB"),
                source_profile,
                destination_profile,
                outputMode="RGB",
            )
            if alpha is not None:
                converted.putalpha(alpha)
            return converted, destination_profile.tobytes()
        except Exception:
            # Invalid/unsupported ICC is explicitly non-fatal in the design.
            return image, None

    def resolve_managed_path(self, relative_path: str) -> Path:
        if not isinstance(relative_path, str) or not relative_path:
            raise InvalidManagedAssetPath("managed asset path must be a string")
        normalized = relative_path.replace("\\", "/")
        pure = PurePosixPath(normalized)
        if pure.is_absolute() or pure.parts[:1] != ("assets",) or len(pure.parts) != 2:
            raise InvalidManagedAssetPath("asset path must be assets/<uuid>.png")
        filename = pure.parts[1]
        if not _canonical_uuid4_filename(filename):
            raise InvalidManagedAssetPath("asset filename must be a canonical system UUID4 PNG")
        assets_root = self.assets_path.resolve()
        candidate = (self.assets_path / filename).resolve()
        if candidate.parent != assets_root:
            raise InvalidManagedAssetPath("asset path escapes the managed assets directory")
        return candidate

    def list_assets(self) -> tuple[Path, ...]:
        if not self.assets_path.exists():
            return ()
        return tuple(
            sorted(
                (
                    path
                    for path in self.assets_path.iterdir()
                    if path.is_file() and _canonical_uuid4_filename(path.name)
                ),
                key=lambda path: path.name,
            )
        )

    def referenced_paths(self, themes: Iterable[object]) -> frozenset[str]:
        references: set[str] = set()
        for theme in themes:
            background = getattr(theme, "background", None)
            relative = getattr(background, "image_path", None)
            if relative:
                try:
                    path = self.resolve_managed_path(relative)
                except InvalidManagedAssetPath:
                    continue
                references.add(f"assets/{path.name}")
        return frozenset(references)

    def delete_asset(self, relative_path: str, referenced_paths: Iterable[str] = ()) -> bool:
        candidate = self.resolve_managed_path(relative_path)
        canonical = f"assets/{candidate.name}"
        referenced: set[str] = set()
        for item in referenced_paths:
            try:
                referenced_path = self.resolve_managed_path(item)
            except InvalidManagedAssetPath:
                continue
            referenced.add(f"assets/{referenced_path.name}")
        if canonical in referenced:
            raise AssetInUseError(f"managed theme asset is still referenced: {canonical}")
        if not candidate.exists():
            return False
        # Resolve again immediately before deletion to defend against path or
        # symlink replacement between listing and confirmation.
        rechecked = self.resolve_managed_path(canonical)
        if rechecked != candidate or rechecked.parent != self.assets_path.resolve():
            raise InvalidManagedAssetPath("managed asset changed before deletion")
        rechecked.unlink()
        return True


__all__ = [
    "MAX_DECODED_PIXELS",
    "MAX_SOURCE_BYTES",
    "SUPPORTED_SOURCE_FORMATS",
    "AssetInUseError",
    "InvalidManagedAssetPath",
    "ManagedThemeAsset",
    "ThemeAssetError",
    "ThemeAssetStore",
    "ThemeImageLimitError",
    "UnsupportedThemeImageError",
]
