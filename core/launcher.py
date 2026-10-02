# -*- coding: utf-8 -*-
"""
启动核心：在后台线程中执行 MC 启动任务
- 自动处理 LWJGL / natives / 主类 / Forge / Fabric 等所有版本差异（交给 minecraft-launcher-lib）
- 启动前自动解压 natives 到 versions/<版本>/natives（库也从这里读，路径固定一致）
- 强制版本隔离：gameDirectory 指向 versions/<版本>/ 目录
- 通过信号把日志实时推送到 UI
"""
import json
import re
import subprocess
import sys
import threading
import traceback
from pathlib import Path

import minecraft_launcher_lib as mcl
from PyQt6.QtCore import QThread, pyqtSignal

from .config import cfg

LAUNCHER_VERSION = "1.0.0"


def _java_major_version(java_path: str) -> int:
    """跑 java -version，解析主版本号（8, 17, 21...），失败返回 -1"""
    try:
        r = subprocess.run(
            [java_path, "-version"],
            capture_output=True, text=True, timeout=10
        )
        out = (r.stderr or r.stdout or "").strip().splitlines()
        # 只看第一行，避免匹配到 warning 里的 version 字样
        first = out[0] if out else ""
        # 匹配: openjdk version "1.8.0_392"  /  version "17.0.10"  /  "21.0.2"
        m = re.search(r'(?:openjdk|java) version "(\d+)(?:\.(\d+))?', first)
        if not m:
            return -1
        major = int(m.group(1))
        if major == 1:
            # 1.8 -> 8
            major = int(m.group(2)) if m.group(2) else 8
        return major
    except Exception:
        return -1


def _parse_mc_version(vid: str):
    """从版本 id 里取前两段数字，忽略 -forge- / -fabric- 后缀。返回 (major, minor) 或 None"""
    m = re.match(r'(\d+)\.(\d+)', vid)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _required_java_major(version_json_path: Path) -> int:
    """
    返回此版本要求的 JDK 主版本号。
    优先读 javaVersion.majorVersion；读不到时按 MC 版本映射：
      <= 1.16.5 -> 8
      1.17 ~ 1.20.4 -> 17
      >= 1.20.5 -> 21
    解析不出来返回 -1（表示未知，不阻断启动）。
    """
    try:
        with open(version_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        jv = data.get("javaVersion", {})
        if isinstance(jv, dict) and "majorVersion" in jv:
            return int(jv["majorVersion"])

        vid = data.get("id", "")
        ver = _parse_mc_version(vid)
        if ver is None:
            return -1
        major_v, minor_v = ver
        # MC 都是 1.x
        if major_v != 1:
            return -1
        if minor_v <= 16:
            return 8
        if minor_v < 20:
            # 1.17 ~ 1.19.x -> 17
            return 17
        if minor_v == 20:
            # 1.20 / 1.20.1~1.20.4 -> 17；1.20.5+ -> 21
            patch_m = re.match(r'1\.20\.(\d+)', vid)
            if patch_m and int(patch_m.group(1)) >= 5:
                return 21
            return 17
        # 1.21+
        return 21
    except Exception:
        return -1


class LaunchWorker(QThread):
    """后台启动线程"""
    log = pyqtSignal(str)
    status = pyqtSignal(str)
    process_finished = pyqtSignal(int)   # 进程结束，带回退出码
    failed = pyqtSignal(str)

    def __init__(self, version, parent=None):
        super().__init__(parent)
        self.version = version
        self._proc: subprocess.Popen | None = None

    def run(self):
        try:
            self._launch()
        except Exception as e:
            tb = traceback.format_exc()
            self.failed.emit(f"启动出错: {e}\n{tb}")

    def stop(self):
        """强制结束游戏（在主线程调用，不阻塞 UI）"""
        proc = self._proc
        if proc and proc.poll() is None:
            proc.terminate()

            def _kill():
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    try:
                        proc.wait()
                    except Exception:
                        pass
            threading.Thread(target=_kill, daemon=True).start()

    def _ensure_natives(self, mc_dir: str) -> bool:
        """
        解压 natives 到 versions/<id>/natives。
        Forge 有 inheritsFrom，库会把 natives 指到父版本目录，
        所以两个位置都解压一份，保证 Java 一定能找到。
        """
        natives_dir = Path(mc_dir) / "versions" / self.version.name / "natives"
        natives_dir.mkdir(parents=True, exist_ok=True)

        # 读版本 JSON 找 inheritsFrom（Forge）
        vjson_path = Path(mc_dir) / "versions" / self.version.name / f"{self.version.name}.json"
        parent_version = None
        try:
            with open(vjson_path, "r", encoding="utf-8") as f:
                vdata = json.load(f)
            parent_version = vdata.get("inheritsFrom")
        except Exception:
            pass

        target_dirs = [natives_dir]
        if parent_version:
            parent_natives = Path(mc_dir) / "versions" / parent_version / "natives"
            target_dirs.append(parent_natives)

        # 平台相关后缀
        if sys.platform == "win32":
            patterns = ["*.dll"]
        elif sys.platform == "darwin":
            patterns = ["*.dylib"]
        else:
            patterns = ["*.so"]

        ok_count = 0
        for tdir in target_dirs:
            tdir.mkdir(parents=True, exist_ok=True)
            # 清空旧文件，防止残留污染
            for old in tdir.iterdir():
                try:
                    if old.is_file():
                        old.unlink()
                except Exception:
                    pass

            self.log.emit(f"解压 natives 到: {tdir}")
            try:
                mcl.natives.extract_natives(
                    self.version.name, mc_dir, str(tdir)
                )
            except Exception as e:
                self.log.emit(f"[警告] 解压到 {tdir} 失败: {e}")
                continue

            dll_count = sum(len(list(tdir.glob(p))) for p in patterns)
            self.log.emit(f"  -> {dll_count} 个文件")
            if dll_count > 0:
                ok_count += 1

        if ok_count == 0:
            self.log.emit("[错误] 所有 natives 目录均为空")
            return False
        return True

    def _launch(self):
        mc_dir = cfg.minecraft_dir
        if not mc_dir:
            self.failed.emit("未设置 Minecraft 根目录")
            return

        vjson = Path(mc_dir) / "versions" / self.version.name / f"{self.version.name}.json"
        if not vjson.exists():
            self.failed.emit(f"版本文件缺失: {vjson}")
            return

        java_path = cfg.java_path
        if not java_path or (java_path != "java" and not Path(java_path).exists()):
            self.failed.emit("未选择有效的 java.exe")
            return

        # Java 版本校验
        cur_java = _java_major_version(java_path)
        need_java = _required_java_major(vjson)
        if cur_java > 0 and need_java > 0 and cur_java < need_java:
            self.failed.emit(
                f"Java 版本过低：当前 JDK {cur_java}，此版本需要 JDK {need_java}。"
                f"请选择更高版本的 Java。"
            )
            return
        self.log.emit(f"Java: JDK {cur_java}（版本要求: {need_java if need_java > 0 else '未知'}）")

        username = cfg.get("username") or "Player"
        # MC 用户名只允许字母数字下划线，去掉空格
        username = re.sub(r'[^A-Za-z0-9_]', '', username) or "Player"
        uuid = (cfg.get("uuid") or "").replace("-", "")
        token = cfg.get("token") or ""

        # 版本隔离
        isolated_game_dir = str(self.version.isolated_dir)
        for sub in ("mods", "saves", "resourcepacks", "shaderpacks", "config", "natives"):
            (Path(isolated_game_dir) / sub).mkdir(parents=True, exist_ok=True)

        self.log.emit(f"========== 启动 InfinityLauncher ==========")
        self.log.emit(f"版本: {self.version.name}  (加载器: {self.version.loader})")
        self.log.emit(f"游戏根目录(隔离): {isolated_game_dir}")
        self.log.emit(f"Java: {java_path}")
        self.log.emit(f"玩家: {username}")

        if not self._ensure_natives(mc_dir):
            self.failed.emit(
                "Natives（LWJGL .dll）未就绪，无法启动游戏。"
                "请确认游戏文件完整，或重新下载此版本。"
            )
            return

        self.log.emit("正在构建启动命令...")

        # 内存 + 编码
        max_mem = int(cfg.get("max_memory", 4096))
        # 显式指定 natives 目录（兜底，防止库推导到父版本路径）
        natives_abs = str(Path(mc_dir) / "versions" / self.version.name / "natives")
        jvm_args = [
            f"-Xmx{max_mem}M",
            f"-Xms{max_mem // 2}M",
            "-Dfile.encoding=UTF-8",
            f"-Djava.library.path={natives_abs}",
        ]
        self.log.emit(f"内存分配: 最大 {max_mem}MB / 初始 {max_mem // 2}MB")
        self.log.emit(f"natives 目录: {natives_abs}")

        # 不写 nativesDirectory：库固定从 versions/<id>/natives 读，
        # _ensure_natives 已解压到同一路径。
        options = {
            "username": username,
            "uuid": uuid or "0" * 32,
            "token": token or "0" * 16,
            "executablePath": java_path,
            "defaultExecutablePath": java_path,
            "jvmArguments": jvm_args,
            "launcherName": "InfinityLauncher",
            "launcherVersion": LAUNCHER_VERSION,
            "gameDirectory": isolated_game_dir,
            "demo": False,
            "customResolution": False,
        }

        self.status.emit("正在生成启动命令...")
        try:
            cmd = mcl.command.get_minecraft_command(
                self.version.name, mc_dir, options
            )
        except Exception as e:
            self.failed.emit(f"生成启动命令失败: {e}")
            return

        self.log.emit(f"主类: {self.version.main_class or '(自动)'}")
        # 打印完整启动命令（排查用）
        self.log.emit("[命令] " + " ".join(f'"{a}"' if " " in a else a for a in cmd))
        self.log.emit("-" * 50)

        # 启动子进程
        try:
            creationflags = 0
            if sys.platform == "win32":
                if cfg.get("show_console", False):
                    creationflags = subprocess.CREATE_NEW_CONSOLE
                else:
                    creationflags = subprocess.CREATE_NO_WINDOW
            self._proc = subprocess.Popen(
                cmd,
                cwd=isolated_game_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
            )
        except Exception as e:
            self.failed.emit(f"无法启动进程: {e}")
            return

        self.status.emit("游戏已启动")
        self.log.emit(f"[PID] {self._proc.pid}")

        if self._proc.stdout:
            for line in self._proc.stdout:
                line = line.rstrip()
                if line:
                    self.log.emit(line)

        self._proc.wait()
        code = self._proc.returncode
        self._proc = None
        self.log.emit("-" * 50)
        self.log.emit(f"游戏进程退出，返回码: {code}")
        self.process_finished.emit(code)
