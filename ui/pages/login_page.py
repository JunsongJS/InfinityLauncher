# -*- coding: utf-8 -*-
"""登录页：离线登录 + 微软登录"""
import threading
import webbrowser

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget
from qfluentwidgets import (
    StrongBodyLabel, BodyLabel, PushButton, InfoBar, InfoBarPosition,
    FluentIcon as FIF, StateToolTip
)

from core.config import cfg
from core.auth import offline_login, MicrosoftLoginWorker
from ui.dialogs import OfflineLoginDialog, MicrosoftCodeDialog


class LoginPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ms_worker: MicrosoftLoginWorker | None = None
        self.ms_thread: QThread | None = None
        self.ms_dialog: MicrosoftCodeDialog | None = None
        self._setup_ui()
        self._show_current_user()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(16)

        title = StrongBodyLabel("账号登录")
        title.setStyleSheet("font-size: 22px;")
        layout.addWidget(title)

        # 当前账号显示 + 退出登录
        user_row = QHBoxLayout()
        self.user_label = BodyLabel()
        self.user_label.setStyleSheet("font-size: 14px; padding: 8px;")
        self.logout_btn = PushButton("退出登录")
        self.logout_btn.setIcon(FIF.CLOSE)
        self.logout_btn.clicked.connect(self._logout)
        user_row.addWidget(self.user_label, stretch=1)
        user_row.addWidget(self.logout_btn)
        layout.addLayout(user_row)

        layout.addSpacing(10)

        # ---- 离线登录 ----
        offline_card = QWidget()
        offline_layout = QVBoxLayout(offline_card)
        offline_layout.setContentsMargins(20, 20, 20, 20)
        offline_layout.setSpacing(10)

        offline_title = StrongBodyLabel("离线登录")
        offline_title.setStyleSheet("font-size: 16px;")
        offline_desc = BodyLabel("无需账号，输入用户名即可进入游戏（仅限单机/私服）")
        offline_desc.setStyleSheet("color: #888;")
        offline_btn = PushButton("离线登录")
        offline_btn.setIcon(FIF.PEOPLE)
        offline_btn.clicked.connect(self._offline_login)
        offline_layout.addWidget(offline_title)
        offline_layout.addWidget(offline_desc)
        offline_layout.addWidget(offline_btn)
        layout.addWidget(offline_card)

        # ---- 微软登录 ----
        ms_card = QWidget()
        ms_layout = QVBoxLayout(ms_card)
        ms_layout.setContentsMargins(20, 20, 20, 20)
        ms_layout.setSpacing(10)

        ms_title = StrongBodyLabel("微软登录")
        ms_title.setStyleSheet("font-size: 16px;")
        ms_desc = BodyLabel("使用正版微软账号登录（支持官方服务器、领域）")
        ms_desc.setStyleSheet("color: #888;")
        self.ms_btn = PushButton("微软登录")
        self.ms_btn.setIcon(FIF.GLOBE)
        self.ms_btn.clicked.connect(self._microsoft_login)
        ms_layout.addWidget(ms_title)
        ms_layout.addWidget(ms_desc)
        ms_layout.addWidget(self.ms_btn)
        layout.addWidget(ms_card)

        layout.addStretch()

    def _show_current_user(self):
        name = cfg.get("username")
        ltype = cfg.get("login_type", "offline")
        if name:
            tag = "正版" if ltype == "microsoft" else "离线"
            self.user_label.setText(f"当前账号: {name}  ({tag})")
            self.logout_btn.setEnabled(True)
        else:
            self.user_label.setText("当前账号: 未登录")
            self.logout_btn.setEnabled(False)

    def _logout(self):
        cfg.set("username", "")
        cfg.set("uuid", "")
        cfg.set("token", "")
        cfg.set("refresh_token", "")
        cfg.set("login_type", "")
        self._show_current_user()
        InfoBar.success(
            "已退出登录", "下次启动游戏前请重新登录",
            parent=self, position=InfoBarPosition.TOP, duration=2000
        )

    # ---------- 离线登录 ----------
    def _offline_login(self):
        dlg = OfflineLoginDialog(self, default_name=cfg.get("username", ""))
        if dlg.exec():
            name = dlg.get_username()
            info = offline_login(name)
            InfoBar.success(
                "登录成功", f"欢迎, {info['username']}!",
                parent=self, position=InfoBarPosition.TOP, duration=2000
            )
            self._show_current_user()

    # ---------- 微软登录 ----------
    def _microsoft_login(self):
        self.ms_btn.setEnabled(False)
        self.ms_btn.setText("正在登录...")

        self.ms_worker = MicrosoftLoginWorker()
        self.ms_thread = QThread()
        self.ms_worker.moveToThread(self.ms_thread)

        self.ms_worker.show_code.connect(self._on_show_code)
        self.ms_worker.log.connect(
            lambda m: print(f"[MS] {m}")  # 也可以弹InfoBar
        )
        self.ms_worker.success.connect(self._on_ms_success)
        self.ms_worker.failed.connect(self._on_ms_failed)
        self.ms_worker.cancelled.connect(self._on_ms_cancelled)
        self.ms_thread.started.connect(self.ms_worker.run)

        self.ms_thread.start()

    def _on_show_code(self, user_code: str, verification_uri: str):
        # 自动打开浏览器
        webbrowser.open(verification_uri)
        # 弹出识别码窗口
        self.ms_dialog = MicrosoftCodeDialog(user_code, verification_uri, self)
        self.ms_dialog.show()

    def _on_ms_success(self, name, uuid, token):
        self._reset_ms_btn()
        self._show_current_user()
        if self.ms_dialog:
            self.ms_dialog.close()
        InfoBar.success(
            "微软登录成功", f"欢迎, {name}!",
            parent=self, position=InfoBarPosition.TOP, duration=3000
        )

    def _on_ms_failed(self, msg: str):
        self._reset_ms_btn()
        if self.ms_dialog:
            self.ms_dialog.close()
        InfoBar.error("登录失败", msg, parent=self, duration=5000)

    def _on_ms_cancelled(self):
        self._reset_ms_btn()

    def _reset_ms_btn(self):
        self.ms_btn.setEnabled(True)
        self.ms_btn.setText("微软登录")
        if self.ms_thread and self.ms_thread.isRunning():
            self.ms_thread.quit()
            self.ms_thread.wait(2000)
