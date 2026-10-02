# -*- coding: utf-8 -*-
"""弹窗：离线登录小窗、微软设备码提示窗"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel
from qfluentwidgets import (
    MessageBoxBase, PushButton, LineEdit, BodyLabel, StrongBodyLabel,
    InfoBar, InfoBarPosition
)
from PyQt6.QtGui import QGuiApplication


class OfflineLoginDialog(MessageBoxBase):
    """离线登录小窗：输入用户名"""

    def __init__(self, parent=None, default_name: str = ""):
        super().__init__(parent)
        self._username = ""
        self.setWindowTitle("离线登录")

        layout = QVBoxLayout()
        layout.setSpacing(12)

        title = StrongBodyLabel("离线登录")
        title.setStyleSheet("font-size: 16px;")
        layout.addWidget(title)

        hint = BodyLabel("请输入你的玩家名称：")
        layout.addWidget(hint)

        self.name_edit = LineEdit()
        self.name_edit.setPlaceholderText("Steve")
        self.name_edit.setText(default_name)
        self.name_edit.setClearButtonEnabled(True)
        layout.addWidget(self.name_edit)

        self.viewLayout.addLayout(layout)

        self.yesButton.setText("登录")
        self.cancelButton.setText("取消")
        self.yesButton.setStyleSheet("background: #009faa; color: white;")
        self.widget.setMinimumWidth(360)

    def validate(self):
        name = self.name_edit.text().strip()
        if not name:
            InfoBar.warning("提示", "请输入用户名", parent=self,
                            position=InfoBarPosition.TOP, duration=2000)
            return False
        self._username = name
        return True

    def get_username(self) -> str:
        return self._username


class MicrosoftCodeDialog(MessageBoxBase):
    """微软登录识别码提示窗（自动复制识别码到剪贴板）"""

    def __init__(self, user_code: str, verification_uri: str, parent=None):
        super().__init__(parent)
        self.user_code = user_code
        self.verification_uri = verification_uri
        self.setWindowTitle("微软账号登录")

        layout = QVBoxLayout()
        layout.setSpacing(10)

        title = StrongBodyLabel("微软账号登录")
        title.setStyleSheet("font-size: 16px;")
        layout.addWidget(title)

        desc = BodyLabel("浏览器已自动打开，请在网页中输入以下识别码：")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self.code_label = QLabel(user_code)
        self.code_label.setStyleSheet(
            "font-size: 28px; font-weight: bold; color: #009faa;"
            "padding: 12px; background: rgba(0,159,170,0.08); border-radius: 8px;"
        )
        self.code_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.code_label)

        link = BodyLabel(f"登录地址: {verification_uri}")
        link.setStyleSheet("color: #666; font-size: 12px;")
        link.setWordWrap(True)
        layout.addWidget(link)

        copy_btn = PushButton("复制识别码")
        copy_btn.clicked.connect(self._copy_code)
        open_btn = PushButton("重新打开浏览器")
        open_btn.clicked.connect(self._open_browser)

        btn_row = QHBoxLayout()
        btn_row.addWidget(copy_btn)
        btn_row.addWidget(open_btn)
        layout.addLayout(btn_row)

        self.viewLayout.addLayout(layout)

        self.cancelButton.setText("关闭")
        self.yesButton.setText("完成")
        self.widget.setMinimumWidth(460)

        # 自动复制识别码
        QGuiApplication.clipboard().setText(user_code)

    def _copy_code(self):
        QGuiApplication.clipboard().setText(self.user_code)

    def _open_browser(self):
        import webbrowser
        webbrowser.open(self.verification_uri)
