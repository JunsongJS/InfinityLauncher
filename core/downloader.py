# -*- coding: utf-8 -*-
"""
下载模块：
  - 列出可用游戏版本（Mojang官方源 / BMCLAPI镜像源）
  - 下载指定版本到指定目录（MC标准目录格式）
  - 支持 Forge / Fabric 安装
  - 后台线程执行，通过信号回报进度与日志
"""
import json
from pathlib import Path

import requests
import minecraft_launcher_lib as mcl
from PyQt6.QtCore import QObject, pyqtSignal

from .config import cfg

# BMCLAPI 镜像（bangbang93）
BMCL_ROOT = "https://bmclapi2.bangbang93.com"
MOJANG_MANIFEST = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"


def _patch_urls_in_json(vjson: dict) -> dict:
    """把版本 JSON 里所有 Mojang 下载 URL 替换为 BMCLAPI"""
    def patch(url: str) -> str:
        if not isinstance(url, str):
            return url
        url = url.replace("https://piston-data.mojang.com", BMCL_ROOT)
        url = url.replace("https://piston-meta.mojang.com", BMCL_ROOT)
        url = url.replace("https://launchermeta.mojang.com", BMCL_ROOT)
        # assets: BMCL 路径是 /assets/<前两位>/<hash>
        url = url.replace("https://resources.download.minecraft.net",
                          f"{BMCL_ROOT}/assets")
        url = url.replace("https://libraries.minecraft.net",
                          f"{BMCL_ROOT}/maven")
        return url

    if isinstance(vjson.get("downloads"), dict):
        for section, info in vjson["downloads"].items():
            if isinstance(info, dict) and "url" in info:
                info["url"] = patch(info["url"])
    for lib in vjson.get("libraries", []):
        dl = lib.get("downloads", {})
        artifact = dl.get("artifact", {})
        if isinstance(artifact, dict) and "url" in artifact:
            artifact["url"] = patch(artifact["url"])
        classifiers = dl.get("classifiers", {})
        if isinstance(classifiers, dict):
            for c in classifiers.values():
                if isinstance(c, dict) and "url" in c:
                    c["url"] = patch(c["url"])
    ai = vjson.get("assetIndex", {})
    if isinstance(ai, dict) and "url" in ai:
        ai["url"] = patch(ai["url"])
    if isinstance(vjson.get("logging"), dict):
        client = vjson["logging"].get("client", {})
        if isinstance(client, dict) and "url" in client:
            client["url"] = patch(client["url"])
    return vjson


class DownloadWorker(QObject):
    """版本下载后台线程"""
    log = pyqtSignal(str)
    progress = pyqtSignal(int, int, str)
    success = pyqtSignal(str)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, version_id: str, mc_dir: str, source: str = "mojang",
                 loader: str = "vanilla", parent=None):
        super().__init__(parent)
        self.version_id = version_id
        self.mc_dir = mc_dir
        self.source = source
        self.loader = loader
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            Path(self.mc_dir).mkdir(parents=True, exist_ok=True)
            self._download_version()
            self.finished.emit()
        except Exception as e:
            self.failed.emit(f"下载失败: {e}")
            self.finished.emit()

    def _make_callback(self):
        return {
            "setStatus": lambda s: self.log.emit(f"[状态] {s}"),
            "setProgress": lambda v: self.progress.emit(v, 100, self.version_id),
            "setMax": lambda maxv: self.progress.emit(0, maxv, "准备..."),
        }

    def _download_version(self):
        self.log.emit(f"开始下载 {self.version_id} (源: {self.source})...")
        callback = self._make_callback()

        if self.source == "bbmcl":
            self._prepare_mirror_json()

        # 统一交给库安装（自动处理 SHA1 校验、natives、依赖）
        self.log.emit("正在安装版本文件...")
        mcl.install.install_minecraft_version(
            self.version_id, self.mc_dir, callback=callback
        )

        self._install_loader(callback)
        self.log.emit(f"{self.version_id} 下载完成！")
        self.success.emit(self.version_id)

    def _prepare_mirror_json(self):
        """镜像源：先从 BMCLAPI 下载并 patch 版本 JSON，再交给库"""
        vdir = Path(self.mc_dir) / "versions" / self.version_id
        vdir.mkdir(parents=True, exist_ok=True)
        target_json = vdir / f"{self.version_id}.json"
        if target_json.exists():
            self.log.emit("版本 JSON 已存在，跳过下载")
            return

        self.log.emit("从 BMCLAPI 获取版本信息...")
        manifest_url = f"{BMCL_ROOT}/mc/game/version_manifest_v2.json"
        r = requests.get(manifest_url, timeout=30)
        r.raise_for_status()
        manifest = r.json()

        target = None
        for v in manifest.get("versions", []):
            if v["id"] == self.version_id:
                target = v
                break
        if not target:
            raise RuntimeError(f"版本 {self.version_id} 在镜像源中不存在")

        version_url = target["url"].replace(
            "piston-meta.mojang.com", "bmclapi2.bangbang93.com"
        )
        self.log.emit(f"下载版本描述: {version_url}")
        r = requests.get(version_url, timeout=30)
        r.raise_for_status()
        vjson = r.json()
        vjson = _patch_urls_in_json(vjson)

        with open(target_json, "w", encoding="utf-8") as f:
            json.dump(vjson, f, ensure_ascii=False, indent=2)
        self.log.emit("版本 JSON 已就位")

    def _install_loader(self, callback):
        java_path = cfg.java_path or None

        if self.loader == "forge":
            self.log.emit("正在查找 Forge 版本...")
            try:
                all_forge = mcl.forge.list_forge_versions()
                prefix = self.version_id + "-"
                matches = [v for v in all_forge if v.startswith(prefix)]
                if not matches:
                    self.log.emit(f"未找到适用于 {self.version_id} 的 Forge 版本")
                    return
                forge_ver = matches[-1]
                self.log.emit(f"安装 Forge: {forge_ver}")
                kwargs = {"callback": callback}
                if java_path:
                    kwargs["java"] = java_path
                mcl.forge.install_forge_version(forge_ver, self.mc_dir, **kwargs)
                self.log.emit(f"Forge {forge_ver} 安装完成")
            except Exception as e:
                self.log.emit(f"Forge 安装失败: {e}")
                self.failed.emit(f"Forge 安装失败: {e}")
                return

        elif self.loader == "fabric":
            self.log.emit("正在安装 Fabric...")
            try:
                loader_ver = mcl.fabric.get_latest_loader_version()
                kwargs = {"callback": callback}
                if java_path:
                    kwargs["java"] = java_path
                mcl.fabric.install_fabric(
                    self.version_id, self.mc_dir,
                    loader_version=loader_ver, **kwargs
                )
                self.log.emit(f"Fabric 安装完成 (loader {loader_ver})")
            except Exception as e:
                self.log.emit(f"Fabric 安装失败: {e}")
                self.failed.emit(f"Fabric 安装失败: {e}")
                return


def fetch_version_list(source: str = "mojang") -> list:
    """获取版本列表（同步，应在后台线程调用）"""
    if source == "bbmcl":
        url = f"{BMCL_ROOT}/mc/game/version_manifest_v2.json"
    else:
        url = MOJANG_MANIFEST
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json().get("versions", [])
