# -*- coding: utf-8 -*-
"""设置页：深浅色模式、全局颜色、自定义背景图"""
import sys
from pathlib import Path

from PyQt6.QtCore import (
    Qt, pyqtSignal, QTimer, QRectF, QPointF
)
from PyQt6.QtGui import (
    QPixmap, QPainter, QTransform, QGuiApplication
)
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QFileDialog,
    QApplication
)
from qfluentwidgets import (
    StrongBodyLabel, BodyLabel, PushButton, ComboBox, SwitchButton,
    InfoBar, InfoBarPosition, FluentIcon as FIF
)

from core.config import cfg


# 预设全局颜色
COLOR_PRESETS = [
    ("青蓝 (默认)", "#009faa"),
    ("赤红", "#e74c3c"),
    ("橙黄", "#e67e22"),
    ("翠绿", "#27ae60"),
    ("紫罗兰", "#9b59b6"),
    ("星空蓝", "#2980b9"),
    ("玫粉", "#e91e63"),
    ("黑金", "#2c3e50"),
]


class SettingsPage(QWidget):
    theme_changed = pyqtSignal(str)   # light / dark
    color_changed = pyqtSignal(str)   # hex
    background_changed = pyqtSignal(str)  # path or ""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_current()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(16)

        title = StrongBodyLabel("设置")
        title.setStyleSheet("font-size: 22px;")
        layout.addWidget(title)

        # ---- 深浅色模式 ----
        theme_row = QHBoxLayout()
        theme_row.addWidget(BodyLabel("深色模式:"))
        self.dark_switch = SwitchButton()
        self.dark_switch.checkedChanged.connect(self._on_theme_toggle)
        theme_row.addWidget(self.dark_switch)
        theme_row.addStretch()
        layout.addLayout(theme_row)

        # ---- 全局颜色 ----
        color_row = QHBoxLayout()
        color_row.addWidget(BodyLabel("全局强调色:"))
        self.color_combo = ComboBox()
        for name, hexv in COLOR_PRESETS:
            self.color_combo.addItem(name, userData=hexv)
        self.color_combo.currentIndexChanged.connect(self._on_color_change)
        color_row.addWidget(self.color_combo, 1)
        layout.addLayout(color_row)

        # ---- 控制台开关 ----
        console_row = QHBoxLayout()
        console_row.addWidget(BodyLabel("显示黑色控制台:"))
        self.console_switch = SwitchButton()
        self.console_switch.setChecked(bool(cfg.get("show_console", False)))
        self.console_switch.checkedChanged.connect(
            lambda c: cfg.set("show_console", bool(c))
        )
        console_row.addWidget(self.console_switch)
        console_row.addStretch()
        layout.addLayout(console_row)

        # ---- 背景图 ----
        bg_title = StrongBodyLabel("背景图片")
        bg_title.setStyleSheet("font-size: 16px; margin-top: 10px;")
        layout.addWidget(bg_title)

        bg_desc = BodyLabel(
            f"把图片放到 {cfg.photo_dir} 文件夹，点击刷新即可选择。\n"
            "选择后自动保存，下次打开启动器保持不变。"
        )
        bg_desc.setStyleSheet("color: #888;")
        layout.addWidget(bg_desc)

        bg_row = QHBoxLayout()
        self.bg_combo = ComboBox()
        self.bg_combo.setMinimumWidth(300)
        self.bg_combo.currentIndexChanged.connect(self._on_bg_change)
        bg_row.addWidget(self.bg_combo, 1)

        refresh_btn = PushButton("刷新")
        refresh_btn.setIcon(FIF.SYNC)
        refresh_btn.clicked.connect(self._refresh_photos)
        clear_bg_btn = PushButton("清除背景")
        clear_bg_btn.clicked.connect(self._clear_bg)
        bg_row.addWidget(refresh_btn)
        bg_row.addWidget(clear_bg_btn)
        layout.addLayout(bg_row)

        layout.addStretch()

        # ---- 彩蛋按钮 ----
        surprise_btn = PushButton("惊喜")
        surprise_btn.setStyleSheet("font-size: 14px; padding: 8px;")
        surprise_btn.clicked.connect(self._surprise)
        layout.addWidget(surprise_btn)

        about = BodyLabel("InfinityLauncher v1.0  |  Python 3.14 + PyQt6 + Fluent Widgets")
        about.setStyleSheet("color: #aaa; font-size: 12px;")
        layout.addWidget(about)

    def _load_current(self):
        # 主题
        theme = cfg.get("theme_mode", "auto")
        from qfluentwidgets import qconfig, Theme
        is_dark = (theme == "dark")
        self.dark_switch.setChecked(is_dark)

        # 颜色
        cur_color = cfg.get("theme_color", "#009faa")
        for i in range(self.color_combo.count()):
            if self.color_combo.itemData(i) == cur_color:
                self.color_combo.setCurrentIndex(i)
                break

        # 背景
        self._refresh_photos()
        cur_bg = cfg.get("background_image", "")
        if cur_bg:
            for i in range(self.bg_combo.count()):
                if self.bg_combo.itemData(i) == cur_bg:
                    self.bg_combo.setCurrentIndex(i)
                    break

    def _on_theme_toggle(self, checked: bool):
        mode = "dark" if checked else "light"
        cfg.set("theme_mode", mode)
        self.theme_changed.emit(mode)

    def _on_color_change(self):
        color = self.color_combo.currentData()
        if color:
            cfg.set("theme_color", color)
            self.color_changed.emit(color)

    def _refresh_photos(self):
        self.bg_combo.blockSignals(True)
        self.bg_combo.clear()
        self.bg_combo.addItem("（无背景）", userData="")
        exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
        if cfg.photo_dir.exists():
            for f in sorted(cfg.photo_dir.iterdir()):
                if f.suffix.lower() in exts:
                    self.bg_combo.addItem(f.name, userData=str(f))
        self.bg_combo.blockSignals(False)

    def _on_bg_change(self):
        path = self.bg_combo.currentData() or ""
        cfg.set("background_image", path)
        self.background_changed.emit(path)

    def _clear_bg(self):
        cfg.set("background_image", "")
        self.bg_combo.setCurrentIndex(0)
        self.background_changed.emit("")
        InfoBar.success("已清除", "背景已恢复默认", parent=self,
                        position=InfoBarPosition.TOP, duration=2000)

    def _surprise(self):
        """彩蛋：窗口原地旋转3秒后退出"""
        app = QApplication.instance()
        main_win = None
        for w in app.topLevelWidgets():
            if w.__class__.__name__ == "MainWindow":
                main_win = w
                break
        if not main_win:
            return

        # 截取主窗口
        pixmap = main_win.grab()
        main_win.hide()

        # 全屏透明旋转层
        screen = QGuiApplication.primaryScreen().geometry()
        rotator = RotateOverlay(pixmap, screen)
        rotator.setGeometry(screen)
        rotator.showFullScreen()
        rotator.start()


class RotateOverlay(QWidget):
    """全屏透明层：把截图旋转绘制在屏幕上"""

    def __init__(self, pixmap: QPixmap, screen_geom, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self._pixmap = pixmap
        self._angle = 0.0
        self._center = QPointF(screen_geom.width() / 2, screen_geom.height() / 2)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._elapsed = 0

    def start(self):
        self._timer.start(16)  # ~60fps

    def _tick(self):
        self._elapsed += 16
        self._angle = (self._elapsed / 3000.0) * 360.0  # 3秒转一圈
        self.update()
        if self._elapsed >= 3000:
            self._timer.stop()
            QApplication.quit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 把截图缩放到合适大小
        pm = self._pixmap.scaled(
            self.width() // 2, self.height() // 2,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        x = self._center.x() - pm.width() / 2
        y = self._center.y() - pm.height() / 2

        transform = QTransform()
        transform.translate(self._center.x(), self._center.y())
        transform.rotate(self._angle)
        transform.translate(-self._center.x(), -self._center.y())
        painter.setTransform(transform)
        painter.drawPixmap(int(x), int(y), pm)
