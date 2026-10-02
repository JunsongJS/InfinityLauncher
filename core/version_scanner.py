# -*- coding: utf-8 -*-
"""
版本扫描模块
同时识别两种目录结构：
  1) 官方标准格式：versions/<版本名>/<版本名>.json
  2) 版本隔离格式：versions/<版本名>/ 目录下存在 version.json 或 <版本名>.json
两种格式在物理结构上其实一致——MC官方启动器本身就用 versions/<name>/<name>.json。
关键区别在于：本启动器强制把 gameDirectory 指向 versions/<版本名>/ 实现隔离。
本模块负责遍历 versions 下所有子目录，找出合法的 .json 版本描述文件，
并解析出主版本号、模组加载器类型（vanilla/forge/fabric/quilt）等信息。
"""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class VersionInfo:
    name: str                       # 版本文件夹名（也是启动标识）
    path: Path                      # versions/<name> 目录
    json_path: Path                 # 版本 json 描述文件
    release_time: str = ""          # 发布时间
    type: str = ""                  # release / snapshot / old_beta / old_alpha
    main_class: str = ""            # 主类
    loader: str = "vanilla"        # vanilla / forge / fabric / quilt / neoforge
    inherits_from: str = ""         # 继承的父版本
    raw: dict = field(default_factory=dict)

    @property
    def isolated_dir(self) -> Path:
        """版本隔离目录：每个版本自己的游戏根目录（存档/模组/资源全隔离）"""
        return self.path

    @property
    def display_name(self) -> str:
        tag = {"forge": "[Forge]", "fabric": "[Fabric]",
               "quilt": "[Quilt]", "neoforge": "[NeoForge]"}.get(self.loader, "")
        return f"{tag} {self.name}".strip()


def detect_loader(version_json: dict) -> str:
    """根据 json 中的 libraries / id 特征判断加载器类型"""
    vid = (version_json.get("id") or "").lower()
    libraries = version_json.get("libraries", []) or []
    lib_names = []
    for lib in libraries:
        name = lib.get("name", "")
        lib_names.append(name.lower())

    joined = " ".join(lib_names)

    if "net.neoforged" in joined or vid.startswith("neoforge"):
        return "neoforge"
    if "net.minecraftforge" in joined or vid.startswith("forge"):
        return "forge"
    if "net.fabricmc" in joined or vid.startswith("fabric"):
        return "fabric"
    if "org.quiltmc" in joined or vid.startswith("quilt"):
        return "quilt"

    # forge/fabric 安装后通常 inheritsFrom 指向原版
    inherits = (version_json.get("inheritsFrom") or "").lower()
    if inherits:
        # 看 id 里有没有提示
        if "forge" in vid:
            return "forge"
        if "fabric" in vid:
            return "fabric"
    return "vanilla"


def scan_versions(minecraft_dir: str) -> List[VersionInfo]:
    """
    扫描 versions 目录，返回所有合法版本。
    兼容：
      - versions/<name>/<name>.json   （官方标准）
      - versions/<name>/version.json  （部分第三方启动器）
    """
    result: List[VersionInfo] = []
    if not minecraft_dir:
        return result

    versions_root = Path(minecraft_dir) / "versions"
    if not versions_root.exists():
        return result

    for sub in sorted(versions_root.iterdir()):
        if not sub.is_dir():
            continue
        # 找版本 json
        json_file = sub / f"{sub.name}.json"
        if not json_file.exists():
            alt = sub / "version.json"
            if alt.exists():
                json_file = alt
            else:
                continue

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        info = VersionInfo(
            name=sub.name,
            path=sub,
            json_path=json_file,
            release_time=data.get("releaseTime", ""),
            type=data.get("type", ""),
            main_class=data.get("mainClass", ""),
            loader=detect_loader(data),
            inherits_from=data.get("inheritsFrom", ""),
            raw=data,
        )
        result.append(info)

    # 排序：按发布时间倒序，找不到时间的排后面
    result.sort(key=lambda x: x.release_time or "", reverse=True)
    return result


def find_java_executables() -> List[str]:
    """尝试自动发现系统中的 java.exe"""
    import subprocess
    candidates = []
    # 常见路径
    common_paths = [
        r"C:\Program Files\Java",
        r"C:\Program Files (x86)\Java",
        r"C:\Program Files\Eclipse Adoptium",
        r"C:\Program Files\Microsoft\jdk",
        os.path.expandvars(r"%APPDATA%\.minecraft\runtime"),
    ]
    for base in common_paths:
        p = Path(base)
        if p.exists():
            for exe in p.rglob("java.exe"):
                try:
                    ver = subprocess.run(
                        [str(exe), "-version"],
                        capture_output=True, text=True, timeout=5
                    )
                    candidates.append(str(exe))
                except Exception:
                    pass
    return candidates
