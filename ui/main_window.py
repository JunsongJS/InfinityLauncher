# -*- coding: utf-8 -*-
"""主窗口：左侧导航栏 + 多页面 + 背景图 + 主题色"""
from pathlib import Path

from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPixmap, QPainter, QColor

from qfluentwidgets import (
    FluentWindow, NavigationItemPosition, FluentIcon as FIF,
    Theme, setTheme, setThemeColor
)

from core.config import cfg
from ui.pages.home_page import HomePage
from ui.pages.login_page import LoginPage
from ui.pages.download_page import DownloadPage
from ui.pages.settings_page import SettingsPage


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("InfinityLauncher")
        self.resize(1000, 700)

        # 背景图
        self._bg_pixmap: QPixmap | None = None

        # 创建页面
        self.home_page = HomePage()
        self.home_page.setObjectName("homePage")
        self.login_page = LoginPage()
        self.login_page.setObjectName("loginPage")
        self.download_page = DownloadPage()
        self.download_page.setObjectName("downloadPage")
        self.settings_page = SettingsPage()
        self.settings_page.setObjectName("settingsPage")

        self._init_navigation()
        self._init_theme()
        self._init_background()
        self._init_animations()

        # 设置页信号
        self.settings_page.theme_changed.connect(self._apply_theme)
        self.settings_page.color_changed.connect(self._apply_color)
        self.settings_page.background_changed.connect(self._apply_background)

    def _init_navigation(self):
        self.addSubInterface(
            self.home_page, FIF.PLAY, "启动",
            position=NavigationItemPosition.TOP
        )
        self.addSubInterface(
            self.login_page, FIF.PEOPLE, "登录",
            position=NavigationItemPosition.TOP
        )
        self.addSubInterface(
            self.download_page, FIF.DOWNLOAD, "下载",
            position=NavigationItemPosition.TOP
        )
        self.addSubInterface(
            self.settings_page, FIF.SETTING, "设置",
            position=NavigationItemPosition.BOTTOM
        )

    def _init_theme(self):
        mode = cfg.get("theme_mode", "auto")
        if mode == "dark":
            setTheme(Theme.DARK)
        elif mode == "light":
            setTheme(Theme.LIGHT)
        color = cfg.get("theme_color", "#009faa")
        setThemeColor(color)

    def _apply_theme(self, mode: str):
        setTheme(Theme.DARK if mode == "dark" else Theme.LIGHT)

    def _apply_color(self, hex_color: str):
        setThemeColor(hex_color)

    def _init_background(self):
        path = cfg.get("background_image", "")
        self._apply_background(path)

    def _apply_background(self, path: str):
        if path and Path(path).exists():
            self._bg_pixmap = QPixmap(path)
        else:
            self._bg_pixmap = None
        self.update()

    def paintEvent(self, event):
        # 先画背景图，再让父类画内容
        if self._bg_pixmap and not self._bg_pixmap.isNull():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            scaled = self._bg_pixmap.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
            painter.fillRect(self.rect(), QColor(0, 0, 0, 110))
            painter.end()
        super().paintEvent(event)

    def _init_animations(self):
        # 窗口淡入：用 windowOpacity（不干扰子控件渲染）
        self.setWindowOpacity(0.0)
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_anim.setDuration(500)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def showEvent(self, event):
        super().showEvent(event)
        self._fade_anim.start()
