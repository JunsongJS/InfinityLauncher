# -*- coding: utf-8 -*-
"""启动页：Java选择 + 版本选择 + 启动按钮 + 日志区"""
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QLinearGradient, QPalette, QColor, QFont
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QFileDialog, QWidget, QListWidgetItem
)
from qfluentwidgets import (
    StrongBodyLabel, BodyLabel, PushButton, ComboBox, LineEdit,
    PlainTextEdit, ListWidget, SpinBox, FluentIcon as FIF, InfoBar, InfoBarPosition
)

from core.config import cfg
from core.version_scanner import scan_versions, VersionInfo
from core.launcher import LaunchWorker


class HomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.versions = []          # List[VersionInfo]
        self.launch_worker: LaunchWorker | None = None
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 20)
        layout.setSpacing(12)

        # ---- 标题：InfinityLauncher 炫彩特效 ----
        self.title_label = BodyLabel("InfinityLauncher")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("""
            font-size: 44px; font-weight: 900;
            font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            color: transparent;
        """)
        # 渐变炫彩文字
        self._hue = 0
        self._hue_timer = QTimer(self)
        self._hue_timer.timeout.connect(self._update_gradient)
        self._hue_timer.start(50)
        self._update_gradient()
        layout.addWidget(self.title_label)

        sub = BodyLabel("Minecraft Java Edition 启动器")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color: #888; font-size: 13px;")
        layout.addWidget(sub)

        # ---- Java 选择 ----
        java_row = QHBoxLayout()
        java_row.setSpacing(8)
        java_row.addWidget(BodyLabel("Java 路径:"))
        self.java_combo = ComboBox()
        self.java_combo.setMinimumWidth(380)
        java_row.addWidget(self.java_combo, 1)
        java_browse = PushButton("浏览...")
        java_browse.setIcon(FIF.FOLDER)
        java_browse.clicked.connect(self._browse_java)
        java_row.addWidget(java_browse)
        layout.addLayout(java_row)

        # ---- MC 目录选择 ----
        mc_row = QHBoxLayout()
        mc_row.setSpacing(8)
        mc_row.addWidget(BodyLabel("MC 目录:"))
        self.mc_dir_edit = LineEdit()
        self.mc_dir_edit.setPlaceholderText("选择 .minecraft 根目录（versions 所在目录）")
        mc_row.addWidget(self.mc_dir_edit, 1)
        mc_browse = PushButton("浏览...")
        mc_browse.setIcon(FIF.FOLDER)
        mc_browse.clicked.connect(self._browse_mc_dir)
        mc_refresh = PushButton("刷新")
        mc_refresh.setIcon(FIF.SYNC)
        mc_refresh.clicked.connect(self._refresh_versions)
        mc_row.addWidget(mc_browse)
        mc_row.addWidget(mc_refresh)
        layout.addLayout(mc_row)

        # ---- 版本搜索 + 列表 ----
        self.search_edit = LineEdit()
        self.search_edit.setPlaceholderText("搜索版本...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._filter_versions)
        layout.addWidget(self.search_edit)

        self.version_list = ListWidget()
        self.version_list.setMaximumHeight(180)
        self.version_list.itemDoubleClicked.connect(lambda _: self._launch())
        layout.addWidget(self.version_list)

        # ---- 内存分配 ----
        mem_row = QHBoxLayout()
        mem_row.setSpacing(8)
        mem_row.addWidget(BodyLabel("最大内存:"))
        self.mem_spin = SpinBox()
        self.mem_spin.setRange(512, 65536)
        self.mem_spin.setSingleStep(512)
        self.mem_spin.setSuffix(" MB")
        self.mem_spin.setValue(4096)
        self.mem_spin.valueChanged.connect(
            lambda v: cfg.set("max_memory", int(v))
        )
        mem_row.addWidget(self.mem_spin)
        mem_row.addStretch()
        layout.addLayout(mem_row)

        # ---- 启动按钮 ----
        self.launch_btn = PushButton("启动游戏")
        self.launch_btn.setIcon(FIF.PLAY)
        self.launch_btn.setStyleSheet(
            "PushButton{font-size:16px; padding:10px; border-radius:8px;}"
        )
        self.launch_btn.clicked.connect(self._launch)
        layout.addWidget(self.launch_btn)

        # ---- 日志区 ----
        log_header = QHBoxLayout()
        log_header.addWidget(StrongBodyLabel("运行日志"))
        log_header.addStretch()
        clear_btn = PushButton("清空日志")
        clear_btn.setIcon(FIF.DELETE)
        clear_btn.clicked.connect(self._clear_log)
        log_header.addWidget(clear_btn)
        layout.addLayout(log_header)

        self.log_view = PlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(5000)
        self.log_view.setStyleSheet("font-family: Consolas, monospace; font-size: 12px;")
        layout.addWidget(self.log_view, 1)

    # ---------- 初始化 ----------
    def _update_gradient(self):
        """炫彩渐变：色相缓慢流动"""
        c1 = QColor.fromHsv(self._hue % 360, 200, 220)
        c2 = QColor.fromHsv((self._hue + 60) % 360, 200, 220)
        c3 = QColor.fromHsv((self._hue + 120) % 360, 200, 220)
        self._hue = (self._hue + 1) % 360
        self.title_label.setStyleSheet(f"""
            font-size: 44px; font-weight: 900;
            font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            color: transparent;
            background: transparent;
        """)
        # 用 palette 做渐变文字
        pal = self.title_label.palette()
        grad = QLinearGradient(0, 0, 400, 0)
        grad.setColorAt(0.0, c1)
        grad.setColorAt(0.5, c2)
        grad.setColorAt(1.0, c3)
        pal.setBrush(QPalette.ColorRole.WindowText, grad)
        self.title_label.setPalette(pal)

    def _load_settings(self):
        java = cfg.java_path
        self.java_combo.addItem(java or "未选择 Java", userData=java)
        self.java_combo.addItem("自动检测 (java)", userData="java")

        mc_dir = cfg.minecraft_dir
        self.mc_dir_edit.setText(mc_dir)
        if mc_dir:
            self._refresh_versions()

        # 恢复内存设置
        saved_mem = cfg.get("max_memory", 4096)
        self.mem_spin.setValue(int(saved_mem))

    # ---------- 事件 ----------
    def _browse_java(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 java.exe", "", "Java (java.exe);;所有文件 (*)"
        )
        if path:
            self.java_combo.addItem(path, userData=path)
            self.java_combo.setCurrentIndex(self.java_combo.count() - 1)
            cfg.java_path = path
            self._log(f"Java 已设置: {path}")

    def _browse_mc_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择 Minecraft 目录")
        if path:
            self.mc_dir_edit.setText(path)
            cfg.minecraft_dir = path
            self._refresh_versions()

    def _refresh_versions(self):
        mc_dir = self.mc_dir_edit.text().strip()
        if not mc_dir:
            return
        cfg.minecraft_dir = mc_dir
        self.versions = scan_versions(mc_dir)
        self._populate_list(self.versions)
        self._log(f"扫描到 {len(self.versions)} 个版本")
        if self.versions:
            InfoBar.success(
                "扫描完成", f"发现 {len(self.versions)} 个版本",
                parent=self, position=InfoBarPosition.TOP, duration=2000
            )

    def _populate_list(self, versions):
        self.version_list.clear()
        for v in versions:
            item = QListWidgetItem(v.display_name)
            item.setData(Qt.ItemDataRole.UserRole, v)
            self.version_list.addItem(item)
        # 恢复选中
        sel = cfg.get("selected_version")
        if sel:
            for i in range(self.version_list.count()):
                if self.version_list.item(i).data(Qt.ItemDataRole.UserRole).name == sel:
                    self.version_list.setCurrentRow(i)
                    break

    def _filter_versions(self, text: str):
        text = text.lower().strip()
        if not text:
            self._populate_list(self.versions)
            return
        filtered = [v for v in self.versions if text in v.name.lower()]
        self._populate_list(filtered)

    def _clear_log(self):
        self.log_view.clear()

    def _log(self, msg: str):
        self.log_view.appendPlainText(msg)

    # ---------- 启动 ----------
    def _launch(self):
        # 检查 Java
        java_data = self.java_combo.currentData()
        if not java_data or java_data == "java":
            java_path = "java"
        else:
            java_path = java_data
        if java_path != "java" and not Path(java_path).exists():
            InfoBar.error("错误", "Java 路径无效，请重新选择", parent=self)
            return
        cfg.java_path = java_path

        # 检查 MC 目录
        mc_dir = self.mc_dir_edit.text().strip()
        if not mc_dir or not Path(mc_dir).exists():
            InfoBar.error("错误", "请选择有效的 MC 目录", parent=self)
            return
        cfg.minecraft_dir = mc_dir

        # 检查版本
        item = self.version_list.currentItem()
        if not item:
            InfoBar.warning("提示", "请先选择一个版本", parent=self)
            return
        version: VersionInfo = item.data(Qt.ItemDataRole.UserRole)
        cfg.set("selected_version", version.name)

        # 检查玩家
        if not cfg.get("username"):
            InfoBar.warning("提示", "请先到登录页设置账号", parent=self)
            return

        # 启动
        self.launch_btn.setEnabled(False)
        self.launch_btn.setText("正在启动...")
        self._log("")

        self.launch_worker = LaunchWorker(version)
        self.launch_worker.log.connect(self._log)
        self.launch_worker.status.connect(
            lambda s: self._log(f"[状态] {s}")
        )
        self.launch_worker.failed.connect(self._on_launch_failed)
        self.launch_worker.process_finished.connect(self._on_launch_finished)
        self.launch_worker.start()

    def _on_launch_failed(self, msg: str):
        self._log(f"[失败] {msg}")
        InfoBar.error("启动失败", msg, parent=self, duration=5000)
        self.launch_btn.setEnabled(True)
        self.launch_btn.setText("启动游戏")

    def _on_launch_finished(self, exit_code: int = 0):
        self.launch_btn.setEnabled(True)
        self.launch_btn.setText("启动游戏")
        if exit_code != 0:
            InfoBar.warning(
                "游戏已退出", f"返回码 {exit_code}（可能崩溃，请查看日志）",
                parent=self, duration=4000
            )
