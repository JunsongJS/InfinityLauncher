# -*- coding: utf-8 -*-
"""下载页：选择源、路径、版本，下载游戏"""
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QFileDialog, QWidget, QListWidgetItem
from qfluentwidgets import (
    StrongBodyLabel, BodyLabel, PushButton, ComboBox, LineEdit,
    ListWidget, ProgressBar, InfoBar, InfoBarPosition,
    FluentIcon as FIF
)

from core.config import cfg
from core.downloader import DownloadWorker, fetch_version_list


class VersionListLoader(QObject):
    """后台加载版本列表（在子线程跑，结果通过信号回主线程）"""
    done = pyqtSignal(list)       # 成功：版本列表
    failed = pyqtSignal(str)      # 失败：错误信息

    def __init__(self, source: str, parent=None):
        super().__init__(parent)
        self.source = source

    def run(self):
        try:
            versions = fetch_version_list(self.source)
            self.done.emit(versions)
        except Exception as e:
            self.failed.emit(str(e))


class DownloadPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.versions = []
        self.dl_thread: QThread | None = None
        self.dl_worker: DownloadWorker | None = None
        self.list_thread: QThread | None = None
        self.list_worker: VersionListLoader | None = None
        self._setup_ui()
        self._load_sources()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 24, 30, 20)
        layout.setSpacing(10)

        title = StrongBodyLabel("下载游戏")
        title.setStyleSheet("font-size: 22px;")
        layout.addWidget(title)

        # ---- 下载源 ----
        src_row = QHBoxLayout()
        src_row.addWidget(BodyLabel("下载源:"))
        self.source_combo = ComboBox()
        self.source_combo.addItem("Mojang 官方源", userData="mojang")
        self.source_combo.addItem("BMCLAPI 镜像 (bangbang93)", userData="bbmcl")
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        src_row.addWidget(self.source_combo, 1)
        layout.addLayout(src_row)

        # ---- 下载路径 ----
        path_row = QHBoxLayout()
        path_row.addWidget(BodyLabel("下载到:"))
        self.path_edit = LineEdit()
        self.path_edit.setPlaceholderText("选择 MC 根目录（将按标准格式创建 versions/ 等）")
        path_row.addWidget(self.path_edit, 1)
        browse_btn = PushButton("浏览...")
        browse_btn.setIcon(FIF.FOLDER)
        browse_btn.clicked.connect(self._browse_path)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        # ---- 加载版本列表 ----
        load_row = QHBoxLayout()
        self.load_btn = PushButton("加载版本列表")
        self.load_btn.setIcon(FIF.DOWNLOAD)
        self.load_btn.clicked.connect(self._load_versions)
        load_row.addWidget(self.load_btn)
        load_row.addStretch()
        layout.addLayout(load_row)

        # ---- 版本列表 ----
        self.version_list = ListWidget()
        self.version_list.setMaximumHeight(260)
        layout.addWidget(self.version_list)

        # ---- 加载器选择 ----
        loader_row = QHBoxLayout()
        loader_row.addWidget(BodyLabel("模组加载器:"))
        self.loader_combo = ComboBox()
        self.loader_combo.addItem("原版 (Vanilla)", userData="vanilla")
        self.loader_combo.addItem("Forge", userData="forge")
        self.loader_combo.addItem("Fabric", userData="fabric")
        loader_row.addWidget(self.loader_combo)
        loader_row.addStretch()
        layout.addLayout(loader_row)

        # ---- 进度条 ----
        self.progress_bar = ProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = BodyLabel("")
        self.status_label.setStyleSheet("color: #888;")
        layout.addWidget(self.status_label)

        # ---- 下载按钮 ----
        self.dl_btn = PushButton("开始下载")
        self.dl_btn.setIcon(FIF.DOWNLOAD)
        self.dl_btn.setStyleSheet("font-size: 15px; padding: 8px;")
        self.dl_btn.clicked.connect(self._start_download)
        layout.addWidget(self.dl_btn)

    def _load_sources(self):
        src = cfg.get("download_source", "mojang")
        idx = 0 if src == "mojang" else 1
        self.source_combo.setCurrentIndex(idx)
        dpath = cfg.get("download_dir") or cfg.minecraft_dir
        if dpath:
            self.path_edit.setText(dpath)

    def _on_source_changed(self):
        src = self.source_combo.currentData()
        cfg.set("download_source", src)

    def _browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择下载目录")
        if path:
            self.path_edit.setText(path)
            cfg.set("download_dir", path)

    def _load_versions(self):
        """用 QThread + 信号加载版本列表，不阻塞UI"""
        self.load_btn.setEnabled(False)
        self.load_btn.setText("加载中...")
        src = self.source_combo.currentData()

        self.list_worker = VersionListLoader(src)
        self.list_thread = QThread()
        self.list_worker.moveToThread(self.list_thread)

        self.list_worker.done.connect(self._on_list_loaded)
        self.list_worker.failed.connect(self._on_list_failed)
        self.list_thread.started.connect(self.list_worker.run)
        self.list_thread.finished.connect(self.list_thread.deleteLater)
        self.list_thread.start()

    def _on_list_loaded(self, versions: list):
        self.versions = versions
        self._populate_list()
        self.load_btn.setEnabled(True)
        self.load_btn.setText("加载版本列表")
        InfoBar.success(
            "加载完成", f"共 {len(versions)} 个版本",
            parent=self, position=InfoBarPosition.TOP, duration=2000
        )

    def _on_list_failed(self, err: str):
        self.load_btn.setEnabled(True)
        self.load_btn.setText("加载版本列表")
        InfoBar.error("加载失败", err, parent=self, duration=4000)

    def _populate_list(self):
        self.version_list.clear()
        for v in self.versions:
            tag = {"release": "正式版", "snapshot": "快照",
                   "old_beta": "远古Beta", "old_alpha": "远古Alpha"}.get(v.get("type", ""), "")
            item = QListWidgetItem(f"  {v['id']}    [{tag}]")
            item.setData(Qt.ItemDataRole.UserRole, v["id"])
            self.version_list.addItem(item)

    def _start_download(self):
        # 如果已有下载在跑，不允许重复点击
        if self.dl_thread and self.dl_thread.isRunning():
            InfoBar.warning("提示", "已有下载任务进行中，请等待完成", parent=self)
            return

        item = self.version_list.currentItem()
        if not item:
            InfoBar.warning("提示", "请先从列表选择一个版本", parent=self)
            return
        version_id = item.data(Qt.ItemDataRole.UserRole)

        dl_path = self.path_edit.text().strip()
        if not dl_path:
            InfoBar.warning("提示", "请选择下载路径", parent=self)
            return

        src = self.source_combo.currentData()
        loader = self.loader_combo.currentData()

        self.dl_btn.setEnabled(False)
        self.dl_btn.setText("下载中...")
        self.progress_bar.setVisible(True)

        self.dl_worker = DownloadWorker(version_id, dl_path, src, loader)
        self.dl_thread = QThread()
        self.dl_worker.moveToThread(self.dl_thread)

        self.dl_worker.progress.connect(self._on_progress)
        self.dl_worker.log.connect(lambda m: self.status_label.setText(m))
        self.dl_worker.success.connect(
            lambda v: InfoBar.success(
                "下载完成", f"版本 {v} 已下载到 {dl_path}",
                parent=self, position=InfoBarPosition.TOP, duration=4000
            )
        )
        self.dl_worker.failed.connect(
            lambda m: InfoBar.error("下载失败", m, parent=self, duration=5000)
        )
        self.dl_worker.finished.connect(self._on_dl_finished)

        self.dl_thread.started.connect(self.dl_worker.run)
        self.dl_thread.finished.connect(self.dl_thread.deleteLater)
        self.dl_thread.start()

    def _on_progress(self, cur, mx, msg):
        if mx > 0:
            self.progress_bar.setMaximum(mx)
            self.progress_bar.setValue(cur)
        self.status_label.setText(msg)

    def _on_dl_finished(self):
        self.dl_btn.setEnabled(True)
        self.dl_btn.setText("开始下载")
        # 线程已通过 finished 信号结束，不需要再 quit
        # deleteLater 会在事件循环中自动清理
