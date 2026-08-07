"""Background composition, shared frames, async generations, and LRU cache."""

from __future__ import annotations

import hashlib
import json
import math
import threading
import time
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor, wait
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator

from PIL import Image, ImageDraw, ImageFilter

from theme_assets import InvalidManagedAssetPath, ThemeAssetStore
from theme_manager import BackgroundDefinition, ThemeDefinition


ALGORITHM_VERSION = "pillow-layered-v2"
DEFAULT_BACKGROUND_CACHE_BYTES = 192 * 1024 * 1024
DEFAULT_GLYPH_CACHE_BYTES = 32 * 1024 * 1024


def _rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    value = hex_color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), alpha


def _position_factors(position: str) -> tuple[float, float]:
    horizontal = 0.0 if position.endswith("left") or position == "left" else 1.0 if position.endswith("right") or position == "right" else 0.5
    vertical = 0.0 if position.startswith("top") or position == "top" else 1.0 if position.startswith("bottom") or position == "bottom" else 0.5
    return horizontal, vertical


def _edge_extend(image: Image.Image, padding: int) -> Image.Image:
    if padding <= 0:
        return image.convert("RGBA").copy()
    source = image.convert("RGBA")
    width, height = source.size
    output = Image.new("RGBA", (width + 2 * padding, height + 2 * padding))
    output.paste(source, (padding, padding))
    output.paste(source.crop((0, 0, width, 1)).resize((width, padding)), (padding, 0))
    output.paste(source.crop((0, height - 1, width, height)).resize((width, padding)), (padding, padding + height))
    output.paste(source.crop((0, 0, 1, height)).resize((padding, height)), (0, padding))
    output.paste(source.crop((width - 1, 0, width, height)).resize((padding, height)), (padding + width, padding))
    for pixel, destination in (
        ((0, 0), (0, 0)),
        ((width - 1, 0), (padding + width, 0)),
        ((0, height - 1), (0, padding + height)),
        ((width - 1, height - 1), (padding + width, padding + height)),
    ):
        corner = Image.new("RGBA", (padding, padding), source.getpixel(pixel))
        output.paste(corner, destination)
    return output


def gaussian_blur(image: Image.Image, logical_radius: float, dpr: float) -> Image.Image:
    radius = float(logical_radius) * float(dpr)
    if radius <= 0:
        return image.convert("RGBA").copy()
    padding = max(1, math.ceil(radius * 3))
    expanded = _edge_extend(image, padding)
    blurred = expanded.filter(ImageFilter.GaussianBlur(radius))
    return blurred.crop((padding, padding, padding + image.width, padding + image.height))


def rounded_clip(
    image: Image.Image,
    logical_radius: float,
    dpr: float,
) -> Image.Image:
    output = image.convert("RGBA").copy()
    mask = Image.new("L", output.size, 0)
    radius = max(0, round(logical_radius * dpr))
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, output.width - 1, output.height - 1), radius=radius, fill=255
    )
    alpha = output.getchannel("A")
    output.putalpha(Image.composite(alpha, Image.new("L", output.size, 0), mask))
    return output


def pil_to_qimage(image: Image.Image):
    from PyQt5.QtGui import QImage

    rgba = image.convert("RGBA")
    raw = rgba.tobytes("raw", "RGBA")
    return QImage(raw, rgba.width, rgba.height, rgba.width * 4, QImage.Format_RGBA8888).copy()


class AssetReaderRegistry:
    def __init__(self):
        self._condition = threading.Condition()
        self._readers: dict[Path, int] = {}

    @contextmanager
    def lease(self, path: Path) -> Iterator[Path]:
        resolved = path.resolve()
        with self._condition:
            self._readers[resolved] = self._readers.get(resolved, 0) + 1
        try:
            yield resolved
        finally:
            with self._condition:
                remaining = self._readers.get(resolved, 1) - 1
                if remaining <= 0:
                    self._readers.pop(resolved, None)
                else:
                    self._readers[resolved] = remaining
                self._condition.notify_all()

    def active_readers(self, path: Path) -> int:
        with self._condition:
            return self._readers.get(path.resolve(), 0)

    def wait_until_released(self, path: Path, timeout: float | None = None) -> bool:
        resolved = path.resolve()
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._condition:
            while self._readers.get(resolved, 0):
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return True


class WeightedLRU:
    def __init__(self, maximum_bytes: int):
        if maximum_bytes <= 0:
            raise ValueError("cache limit must be positive")
        self.maximum_bytes = int(maximum_bytes)
        self.current_bytes = 0
        self._items: OrderedDict[Any, tuple[Any, int]] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: Any) -> Any | None:
        with self._lock:
            item = self._items.pop(key, None)
            if item is None:
                return None
            self._items[key] = item
            return item[0]

    def put(self, key: Any, value: Any, size: int) -> None:
        size = max(0, int(size))
        with self._lock:
            previous = self._items.pop(key, None)
            if previous:
                self.current_bytes -= previous[1]
            if size > self.maximum_bytes:
                return
            self._items[key] = (value, size)
            self.current_bytes += size
            while self.current_bytes > self.maximum_bytes and self._items:
                _, (_, removed_size) = self._items.popitem(last=False)
                self.current_bytes -= removed_size

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            self.current_bytes = 0

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)


class BackgroundComposer:
    def __init__(
        self,
        asset_store: ThemeAssetStore | None = None,
        reader_registry: AssetReaderRegistry | None = None,
    ):
        self.asset_store = asset_store
        self.reader_registry = reader_registry or AssetReaderRegistry()

    def compose(
        self,
        theme: ThemeDefinition,
        logical_size: tuple[int, int],
        dpr: float = 1.0,
    ) -> Image.Image:
        if dpr <= 0 or any(value <= 0 for value in logical_size):
            raise ValueError("logical size and DPR must be positive")
        size = tuple(max(1, round(value * dpr)) for value in logical_size)
        canvas = Image.new("RGBA", size, _rgba(theme.palette.background))
        image = self._load_background(theme.background)
        if image is not None:
            fitted = self._fit(image, size, theme.background)
            if theme.background.image_opacity < 1.0:
                alpha = fitted.getchannel("A").point(
                    lambda value: round(value * theme.background.image_opacity)
                )
                fitted.putalpha(alpha)
            canvas = Image.alpha_composite(canvas, fitted)
        if theme.background.mask_opacity > 0:
            overlay = Image.new(
                "RGBA",
                size,
                _rgba(
                    theme.background.mask_color,
                    round(255 * theme.background.mask_opacity),
                ),
            )
            canvas = Image.alpha_composite(canvas, overlay)
        return canvas

    def _load_background(self, background: BackgroundDefinition) -> Image.Image | None:
        if not background.image_path or self.asset_store is None:
            return None
        try:
            path = self.asset_store.resolve_managed_path(background.image_path)
        except InvalidManagedAssetPath:
            return None
        if not path.is_file():
            return None
        with self.reader_registry.lease(path):
            try:
                with Image.open(path) as opened:
                    opened.seek(0)
                    opened.load()
                    return opened.convert("RGBA")
            except OSError:
                return None

    @staticmethod
    def _fit(
        source: Image.Image,
        size: tuple[int, int],
        background: BackgroundDefinition,
    ) -> Image.Image:
        source = source.convert("RGBA")
        target_width, target_height = size
        x_factor, y_factor = _position_factors(background.position)
        output = Image.new("RGBA", size, (0, 0, 0, 0))
        if background.fit_mode == "stretch":
            return source.resize(size, Image.Resampling.LANCZOS)
        if background.fit_mode == "tile":
            offset_x = round((target_width % source.width) * x_factor) - source.width
            offset_y = round((target_height % source.height) * y_factor) - source.height
            for y in range(offset_y, target_height, source.height):
                for x in range(offset_x, target_width, source.width):
                    output.alpha_composite(source, (x, y))
            return output

        scale_x = target_width / source.width
        scale_y = target_height / source.height
        scale = max(scale_x, scale_y) if background.fit_mode == "cover" else min(scale_x, scale_y)
        scaled_size = (
            max(1, round(source.width * scale)),
            max(1, round(source.height * scale)),
        )
        resized = source.resize(scaled_size, Image.Resampling.LANCZOS)
        x = round((target_width - resized.width) * x_factor)
        y = round((target_height - resized.height) * y_factor)
        output.alpha_composite(resized, (x, y))
        return output

    def content_hash(self, theme: ThemeDefinition) -> str:
        if not theme.background.image_path or self.asset_store is None:
            return "none"
        try:
            path = self.asset_store.resolve_managed_path(theme.background.image_path)
        except InvalidManagedAssetPath:
            return "invalid"
        if not path.is_file():
            return "missing"
        digest = hashlib.sha256()
        with self.reader_registry.lease(path), path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class RenderKey:
    generation: int
    theme_revision: int
    render_revision: int
    logical_size: tuple[int, int]
    dpr: float
    asset_hash: str
    background_signature: str
    algorithm_version: str = ALGORITHM_VERSION


@dataclass(frozen=True, slots=True)
class RenderedFrame:
    key: RenderKey
    image: Any
    content_image: Any | None = None
    sidebar_image: Any | None = None

    @property
    def byte_size(self) -> int:
        images = (self.image, self.content_image, self.sidebar_image)
        unique = {id(image): image for image in images if image is not None}
        return sum(image.width() * image.height() * 4 for image in unique.values())

    def material_image(self, material: str = "background") -> Any:
        if material == "content" and self.content_image is not None:
            return self.content_image
        if material == "sidebar" and self.sidebar_image is not None:
            return self.sidebar_image
        return self.image

    def draw(
        self,
        painter,
        target_rect,
        source_rect=None,
        *,
        material: str = "background",
        logical_source: bool = False,
    ) -> None:
        from PyQt5.QtCore import QRectF

        target = QRectF(target_rect)
        image = self.material_image(material)
        source = (
            QRectF(0, 0, image.width(), image.height())
            if source_rect is None
            else QRectF(source_rect)
        )
        if logical_source:
            dpr = self.key.dpr
            source = QRectF(
                source.x() * dpr,
                source.y() * dpr,
                source.width() * dpr,
                source.height() * dpr,
            )
        painter.drawImage(target, image, source)


@dataclass(frozen=True, slots=True)
class _RenderRequest:
    generation: int
    theme: ThemeDefinition
    theme_revision: int
    render_revision: int
    logical_size: tuple[int, int]
    dpr: float
    callback: Callable[[RenderedFrame], None] | None
    error_callback: Callable[[Exception], None] | None

    @property
    def signature(self) -> tuple[Any, ...]:
        return (
            self.generation,
            self.theme_revision,
            self.render_revision,
            self.logical_size,
            self.dpr,
            self.theme.visual_signature(),
        )


class ThemeRenderEngine:
    def __init__(
        self,
        composer: BackgroundComposer,
        *,
        maximum_workers: int = 2,
        background_cache_bytes: int = DEFAULT_BACKGROUND_CACHE_BYTES,
        glyph_cache_bytes: int = DEFAULT_GLYPH_CACHE_BYTES,
        throttle_ms: int = 50,
    ):
        self.composer = composer
        self.background_cache = WeightedLRU(background_cache_bytes)
        self.glyph_cache = WeightedLRU(glyph_cache_bytes)
        self._executor = ThreadPoolExecutor(max_workers=maximum_workers, thread_name_prefix="theme-render")
        self._lock = threading.RLock()
        self._generation = 0
        self._current_signature: tuple[Any, ...] | None = None
        self._current_frame: RenderedFrame | None = None
        self._futures: set[Future] = set()
        self._closed = False
        self._throttle_seconds = max(0, throttle_ms) / 1000.0
        self._last_submit = 0.0
        self._pending_timer: threading.Timer | None = None
        self._pending_arguments: tuple | None = None

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    @property
    def current_frame(self) -> RenderedFrame | None:
        with self._lock:
            return self._current_frame

    def request(
        self,
        theme: ThemeDefinition,
        *,
        theme_revision: int,
        render_revision: int,
        logical_size: tuple[int, int],
        dpr: float,
        callback: Callable[[RenderedFrame], None] | None = None,
        error_callback: Callable[[Exception], None] | None = None,
    ) -> int:
        with self._lock:
            if self._closed:
                raise RuntimeError("theme render engine is closed")
            self._generation += 1
            request = _RenderRequest(
                self._generation,
                theme,
                theme_revision,
                render_revision,
                tuple(logical_size),
                float(dpr),
                callback,
                error_callback,
            )
            self._current_signature = request.signature
            self._last_submit = time.monotonic()
            future = self._executor.submit(self._render_request, request)
            self._futures.add(future)
            future.add_done_callback(self._future_finished)
            return request.generation

    def request_throttled(self, *args, **kwargs) -> None:
        with self._lock:
            if self._closed:
                return
            now = time.monotonic()
            delay = self._throttle_seconds - (now - self._last_submit)
            if delay <= 0 and self._pending_timer is None:
                submit_now = True
            else:
                submit_now = False
                self._pending_arguments = (args, kwargs)
                if self._pending_timer is None:
                    self._pending_timer = threading.Timer(max(0, delay), self._flush_throttled)
                    self._pending_timer.daemon = True
                    self._pending_timer.start()
        if submit_now:
            self.request(*args, **kwargs)

    def _flush_throttled(self) -> None:
        with self._lock:
            pending = self._pending_arguments
            self._pending_arguments = None
            self._pending_timer = None
            closed = self._closed
        if pending and not closed:
            self.request(*pending[0], **pending[1])

    def _render_request(self, request: _RenderRequest) -> None:
        try:
            asset_hash = self.composer.content_hash(request.theme)
            background_signature = json.dumps(
                {
                    "background_color": request.theme.palette.background,
                    "background": request.theme.background.to_dict(),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            material_signature = json.dumps(
                {
                    "content_enabled": request.theme.effects.content_enabled,
                    "content_blur_radius": request.theme.effects.content_blur_radius,
                    "sidebar_enabled": request.theme.effects.sidebar_enabled,
                    "sidebar_blur_radius": request.theme.effects.sidebar_blur_radius,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            cache_key = (
                request.theme_revision,
                request.render_revision,
                request.logical_size,
                request.dpr,
                asset_hash,
                background_signature,
                material_signature,
                ALGORITHM_VERSION,
            )
            cached_images = self.background_cache.get(cache_key)
            if cached_images is None:
                composed = self.composer.compose(
                    request.theme, request.logical_size, request.dpr
                )
                image = pil_to_qimage(composed)
                if request.theme.effects.content_enabled:
                    content_image = pil_to_qimage(
                        gaussian_blur(
                            composed,
                            request.theme.effects.content_blur_radius,
                            request.dpr,
                        )
                    )
                else:
                    content_image = image

                sidebar_width = max(
                    1,
                    min(
                        composed.width,
                        round(request.logical_size[0] * 0.1 * request.dpr),
                    ),
                )
                sidebar_source = composed.crop(
                    (0, 0, sidebar_width, composed.height)
                )
                if request.theme.effects.sidebar_enabled:
                    sidebar_source = gaussian_blur(
                        sidebar_source,
                        request.theme.effects.sidebar_blur_radius,
                        request.dpr,
                    )
                sidebar_image = pil_to_qimage(sidebar_source)
                cached_images = (image, content_image, sidebar_image)
                unique_images = {
                    id(candidate): candidate for candidate in cached_images
                }
                self.background_cache.put(
                    cache_key,
                    cached_images,
                    sum(
                        candidate.width() * candidate.height() * 4
                        for candidate in unique_images.values()
                    ),
                )
            image, content_image, sidebar_image = cached_images
            key = RenderKey(
                request.generation,
                request.theme_revision,
                request.render_revision,
                request.logical_size,
                request.dpr,
                asset_hash,
                background_signature,
            )
            frame = RenderedFrame(key, image, content_image, sidebar_image)
            with self._lock:
                install = (
                    not self._closed
                    and request.generation == self._generation
                    and request.signature == self._current_signature
                )
                if install:
                    self._current_frame = frame
            if install and request.callback:
                request.callback(frame)
        except Exception as exc:
            with self._lock:
                report = not self._closed and request.generation == self._generation
            if report and request.error_callback:
                request.error_callback(exc)

    def _future_finished(self, future: Future) -> None:
        with self._lock:
            self._futures.discard(future)

    def frame_or_solid_fallback(
        self,
        theme: ThemeDefinition,
        logical_size: tuple[int, int],
        dpr: float,
    ) -> Any:
        with self._lock:
            if self._current_frame is not None:
                return self._current_frame.image
        size = tuple(max(1, round(value * dpr)) for value in logical_size)
        return pil_to_qimage(Image.new("RGBA", size, _rgba(theme.palette.background)))

    def wait_idle(self, timeout: float | None = None) -> bool:
        with self._lock:
            futures = tuple(self._futures)
        if not futures:
            return True
        _, pending = wait(futures, timeout=timeout)
        return not pending

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._generation += 1
            timer = self._pending_timer
            self._pending_timer = None
            self._pending_arguments = None
            futures = tuple(self._futures)
        if timer:
            timer.cancel()
        for future in futures:
            future.cancel()
        self._executor.shutdown(wait=True, cancel_futures=True)
        with self._lock:
            self._futures.clear()
            self._current_signature = None


__all__ = [
    "ALGORITHM_VERSION",
    "AssetReaderRegistry",
    "BackgroundComposer",
    "RenderKey",
    "RenderedFrame",
    "ThemeRenderEngine",
    "WeightedLRU",
    "gaussian_blur",
    "pil_to_qimage",
    "rounded_clip",
]
