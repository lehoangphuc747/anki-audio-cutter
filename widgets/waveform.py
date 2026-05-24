# -*- coding: utf-8 -*-
"""
Custom Waveform Slider widget for Audio Card Cutter.
"""
from aqt.qt import (
    QAbstractSlider, QColor, QPainter, QPen, QSizePolicy, Qt
)

from ..player import HAS_MEDIA
from ..constants import WAVEFORM_BAR_WIDTH, WAVEFORM_BAR_SPACING


class AudioWaveformWidget(QAbstractSlider):
    """Custom interactive widget displaying audio waveform with Audacity-like selection."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setOrientation(Qt.Orientation.Horizontal)
        self._waveform_data: list[float] = []
        self._binned_data: list[float] = []
        self._binned_width: int = -1
        self._region_start_ms: int = -1
        self._region_end_ms: int = -1
        self._is_selecting: bool = False
        self._drag_start_val: int = 0
        self._region_callback = None
        self._queued_regions: list[tuple[int, int]] = []

        self.setMinimumHeight(64)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

    def set_region_callback(self, callback) -> None:
        self._region_callback = callback

    def set_waveform_data(self, data: list[float]) -> None:
        self._waveform_data = data
        self._binned_data.clear()
        self._binned_width = -1
        self.update()

    def set_queued_regions(self, regions: list[tuple[int, int]]) -> None:
        self._queued_regions = regions
        self.update()

    def set_region(self, start_ms: int, end_ms: int) -> None:
        self._region_start_ms = start_ms
        self._region_end_ms = end_ms
        self.update()

    def clear_region(self) -> None:
        self._region_start_ms = -1
        self._region_end_ms = -1
        self.update()

    def x_to_value(self, x: int) -> int:
        w = self.width()
        if w <= 0:
            return 0
        ratio = max(0.0, min(float(x) / w, 1.0))
        val_range = self.maximum() - self.minimum()
        return self.minimum() + int(ratio * val_range)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_selecting = True
            self._drag_start_val = self.x_to_value(event.pos().x())
            self.setValue(self._drag_start_val)
            self.sliderPressed.emit()
            if HAS_MEDIA:
                self.sliderMoved.emit(self._drag_start_val)
            self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._is_selecting:
            val = self.x_to_value(event.pos().x())
            if abs(val - self._drag_start_val) > 150:
                s = min(self._drag_start_val, val)
                e = max(self._drag_start_val, val)
                self.set_region(s, e)
                if self._region_callback:
                    self._region_callback(s / 1000.0, e / 1000.0)
            else:
                self.setValue(val)
                self.sliderMoved.emit(val)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_selecting = False
            val = self.x_to_value(event.pos().x())
            self.sliderReleased.emit()
            if abs(val - self._drag_start_val) < 150:
                self.setValue(val)
                self.sliderMoved.emit(val)
            else:
                s = min(self._drag_start_val, val)
                e = max(self._drag_start_val, val)
                self.set_region(s, e)
                if self._region_callback:
                    self._region_callback(s / 1000.0, e / 1000.0)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            # Select all / Reset selection to full range
            self.set_region(self.minimum(), self.maximum())
            if self._region_callback:
                self._region_callback(self.minimum() / 1000.0, self.maximum() / 1000.0)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # 1. Background (match current theme automatically)
        bg_color = self.palette().color(self.backgroundRole())
        if bg_color.lightness() < 128:
            bg_color = QColor(30, 30, 30)
        else:
            bg_color = QColor(245, 245, 245)
        painter.fillRect(0, 0, w, h, bg_color)

        painter.setPen(QColor(180, 180, 180, 80))
        painter.drawRect(0, 0, w - 1, h - 1)

        # 1.5. Draw Queued Regions (Background translucent green highlights + dashed borders)
        val_range = self.maximum() - self.minimum()
        if val_range > 0 and self._queued_regions:
            queued_overlay_color = QColor(76, 175, 80, 30)  # Translucent green/teal
            dashed_pen = QPen(QColor(76, 175, 80, 180))
            dashed_pen.setStyle(Qt.PenStyle.DashLine)
            dashed_pen.setWidth(1)

            for s_ms, e_ms in self._queued_regions:
                if s_ms >= 0 and e_ms >= 0 and e_ms > s_ms:
                    s_ratio = (s_ms - self.minimum()) / val_range
                    e_ratio = (e_ms - self.minimum()) / val_range
                    qx_start = int(s_ratio * w)
                    qx_end = int(e_ratio * w)
                    
                    # Fill background of queued region
                    painter.fillRect(qx_start, 0, qx_end - qx_start, h, queued_overlay_color)
                    
                    # Draw vertical boundary lines
                    painter.save()
                    painter.setPen(dashed_pen)
                    painter.drawLine(qx_start, 0, qx_start, h)
                    painter.drawLine(qx_end, 0, qx_end, h)
                    painter.restore()

        # 2. Draw Waveform
        if self._waveform_data:
            step = WAVEFORM_BAR_WIDTH + WAVEFORM_BAR_SPACING
            num_bars = w // step

            if self._binned_width != w or len(self._binned_data) != num_bars:
                self._binned_data = self._bin_data(self._waveform_data, num_bars)
                self._binned_width = w

            base_pen = QColor(160, 160, 160, 130)
            active_pen = QColor(33, 150, 243)

            val_range = self.maximum() - self.minimum()
            x_start = -1
            x_end = -1
            if val_range > 0 and self._region_start_ms >= 0 and self._region_end_ms >= 0:
                s_ratio = (self._region_start_ms - self.minimum()) / val_range
                e_ratio = (self._region_end_ms - self.minimum()) / val_range
                x_start = int(s_ratio * w)
                x_end = int(e_ratio * w)

            # Draw inactive base waveform
            painter.setPen(base_pen)
            for i in range(num_bars):
                x = i * step + WAVEFORM_BAR_WIDTH // 2
                val = self._binned_data[i]
                bar_h = int(val * h * 0.8)
                y_start = (h - bar_h) // 2
                painter.drawLine(x, y_start, x, y_start + bar_h)

            # Draw active waveform inside clip rect & highlight overlay
            if x_start >= 0 and x_end >= 0 and x_end > x_start:
                highlight_color = QColor(33, 150, 243, 40)
                painter.fillRect(x_start, 0, x_end - x_start, h, highlight_color)

                painter.save()
                painter.setClipRect(x_start, 0, x_end - x_start, h)
                painter.setPen(active_pen)
                for i in range(num_bars):
                    x = i * step + WAVEFORM_BAR_WIDTH // 2
                    val = self._binned_data[i]
                    bar_h = int(val * h * 0.8)
                    y_start = (h - bar_h) // 2
                    painter.drawLine(x, y_start, x, y_start + bar_h)
                painter.restore()

        # 3. Draw Playhead
        val_range = self.maximum() - self.minimum()
        if val_range > 0:
            current_ratio = (self.value() - self.minimum()) / val_range
            playhead_x = int(current_ratio * w)
            painter.setPen(QColor(244, 67, 54))  # Red Playhead
            painter.drawLine(playhead_x, 0, playhead_x, h)

    def _bin_data(self, data: list[float], num_bins: int) -> list[float]:
        if not data:
            return [0.0] * num_bins
        n = len(data)
        if n <= num_bins:
            return data + [0.0] * (num_bins - n)

        bin_size = n / num_bins
        bins = []
        for i in range(num_bins):
            start_idx = int(i * bin_size)
            end_idx = int((i + 1) * bin_size)
            chunk = data[start_idx:end_idx]
            if chunk:
                bins.append(max(chunk))
            else:
                bins.append(0.0)
        return bins

    def wheelEvent(self, event) -> None:  # noqa: N802
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            angle = event.angleDelta().y()
            # The parent of self inside QScrollArea is the viewport, and its parent is the QScrollArea, and its parent is the dialog.
            # But in ui.py we set parent of AudioWaveformWidget to self (the dialog).
            # Let's check both self.parent() and self.window() or parent of scroll area to be safe.
            # We can find the dialog by traversing parent() or checking hasattr.
            target = self.parent()
            for _ in range(5):
                if target and hasattr(target, "change_zoom"):
                    break
                if target:
                    target = target.parent()
            if target and hasattr(target, "change_zoom"):
                target.change_zoom(angle > 0)
            event.accept()
        else:
            event.ignore()
