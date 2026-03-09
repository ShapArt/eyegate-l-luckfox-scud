from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import cv2  # type: ignore
import numpy as np

from vision.types import BoundingBox


@dataclass
class PeopleCounterConfig:
    bg_history: int = 200
    bg_var_threshold: float = 25.0
    bg_detect_shadows: bool = True
    people_min_area: int = 1200
    dilate_kernel: int = 5
    erode_kernel: int = 3
    use_morphology: bool = True
    # Heuristics to reduce false-positive "confetti" blobs on real cameras.
    # Ratios scale with the incoming frame size, so defaults work for 480p..1080p.
    min_aspect_ratio: float = 0.25
    max_aspect_ratio: float = 1.8
    min_area_ratio: float = 0.015
    min_width_ratio: float = 0.06
    min_height_ratio: float = 0.18
    # Filter blobs that "stick" to borders (often camera noise / lighting flicker).
    border_margin_ratio: float = 0.02
    # Filter low-density contours (thin stripes / edge speckle).
    min_extent: float = 0.18
    # Merge nearby/overlapping blobs into one silhouette (fragmented bodies).
    merge_margin_ratio: float = 0.02
    mask_median_blur: int = 7
    frame_gaussian_blur: int = 7
    dominant_second_area_ratio: float = 0.35
    max_boxes_for_overlay: int = 8


class PeopleCounter:
    """Silhouette-based people counter for static camera."""

    def __init__(self, cfg: Optional[PeopleCounterConfig] = None) -> None:
        self._cfg = cfg or PeopleCounterConfig()
        self._subtractor = cv2.createBackgroundSubtractorMOG2(
            history=self._cfg.bg_history,
            varThreshold=self._cfg.bg_var_threshold,
            detectShadows=self._cfg.bg_detect_shadows,
        )
        self._kernel_dilate = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (self._cfg.dilate_kernel,) * 2
        )
        self._kernel_erode = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (self._cfg.erode_kernel,) * 2
        )

    def _preprocess(self, mask: np.ndarray) -> np.ndarray:
        """Apply morphology to reduce noise; separated for testability."""
        if self._cfg.mask_median_blur and self._cfg.mask_median_blur >= 3:
            k = int(self._cfg.mask_median_blur)
            if k % 2 == 0:
                k += 1
            mask = cv2.medianBlur(mask, k)
        _, fg = cv2.threshold(mask, 200, 255, cv2.THRESH_BINARY)
        if self._cfg.use_morphology:
            # Open removes speckle; close reconnects fragmented silhouettes.
            fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, self._kernel_erode, iterations=1)
            fg = cv2.morphologyEx(
                fg, cv2.MORPH_CLOSE, self._kernel_dilate, iterations=1
            )
        return fg

    def _filter_blobs(
        self, contours, frame_w: int, frame_h: int
    ) -> Tuple[int, list[BoundingBox]]:
        frame_area = max(1, int(frame_w) * int(frame_h))
        min_area = max(
            self._cfg.people_min_area, int(frame_area * float(self._cfg.min_area_ratio))
        )
        min_w = max(1, int(frame_w * float(self._cfg.min_width_ratio)))
        min_h = max(1, int(frame_h * float(self._cfg.min_height_ratio)))
        border_margin = max(
            0, int(min(frame_w, frame_h) * float(self._cfg.border_margin_ratio))
        )

        boxes: list[BoundingBox] = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            if w < min_w or h < min_h:
                continue
            if border_margin > 0:
                if x <= border_margin or y <= border_margin:
                    continue
                if (x + w) >= (frame_w - border_margin) or (y + h) >= (
                    frame_h - border_margin
                ):
                    continue
            aspect = w / max(h, 1)
            if not (self._cfg.min_aspect_ratio <= aspect <= self._cfg.max_aspect_ratio):
                continue
            extent = float(area) / float(max(1, int(w) * int(h)))
            if extent < float(self._cfg.min_extent):
                continue
            boxes.append(BoundingBox(x=x, y=y, w=w, h=h, score=float(area)))
        return len(boxes), boxes

    @staticmethod
    def _boxes_touch_or_close(a: BoundingBox, b: BoundingBox, margin: int) -> bool:
        ax1, ay1, ax2, ay2 = int(a.x), int(a.y), int(a.x + a.w), int(a.y + a.h)
        bx1, by1, bx2, by2 = int(b.x), int(b.y), int(b.x + b.w), int(b.y + b.h)
        return not (
            ax2 + margin < bx1
            or bx2 + margin < ax1
            or ay2 + margin < by1
            or by2 + margin < ay1
        )

    def _merge_boxes(
        self, boxes: list[BoundingBox], frame_w: int, frame_h: int
    ) -> list[BoundingBox]:
        if len(boxes) <= 1:
            return boxes
        margin = max(
            0, int(min(frame_w, frame_h) * float(self._cfg.merge_margin_ratio))
        )
        merged: list[BoundingBox] = []
        for box in boxes:
            merged_into = False
            for idx, existing in enumerate(merged):
                if not self._boxes_touch_or_close(existing, box, margin=margin):
                    continue
                x1 = min(existing.x, box.x)
                y1 = min(existing.y, box.y)
                x2 = max(existing.x + existing.w, box.x + box.w)
                y2 = max(existing.y + existing.h, box.y + box.h)
                merged[idx] = BoundingBox(
                    x=int(x1),
                    y=int(y1),
                    w=int(x2 - x1),
                    h=int(y2 - y1),
                    score=float((existing.score or 0.0) + (box.score or 0.0)),
                )
                merged_into = True
                break
            if not merged_into:
                merged.append(box)
        return merged

    def detect(self, frame: np.ndarray) -> Tuple[int, list[BoundingBox]]:
        """Return (people_count, silhouette_boxes) for overlay/debug."""
        src = frame
        if self._cfg.frame_gaussian_blur and self._cfg.frame_gaussian_blur >= 3:
            k = int(self._cfg.frame_gaussian_blur)
            if k % 2 == 0:
                k += 1
            src = cv2.GaussianBlur(frame, (k, k), 0)

        mask = self._subtractor.apply(src)
        fg = self._preprocess(mask)
        contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        h, w = frame.shape[:2]
        count, boxes = self._filter_blobs(contours, frame_w=w, frame_h=h)
        if boxes:
            boxes.sort(key=lambda b: int(b.w) * int(b.h), reverse=True)
            boxes = self._merge_boxes(boxes, frame_w=w, frame_h=h)
            count = len(boxes)
            # If we have many blobs but only one is dominant, treat it as a single person
            # and keep only the dominant box for overlay.
            if len(boxes) >= 4:
                area1 = int(boxes[0].w) * int(boxes[0].h)
                area2 = int(boxes[1].w) * int(boxes[1].h) if len(boxes) > 1 else 0
                if area1 > 0 and (area2 / area1) < float(
                    self._cfg.dominant_second_area_ratio
                ):
                    boxes = boxes[:1]
                    count = 1

            max_boxes = int(self._cfg.max_boxes_for_overlay or 0)
            if max_boxes > 0 and len(boxes) > max_boxes:
                boxes = boxes[:max_boxes]
        return count, boxes

    def count(self, frame: np.ndarray) -> int:
        count, _ = self.detect(frame)
        return count
