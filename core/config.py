# -*- coding: utf-8 -*-
"""全局配置管理，所有设置持久化到 config.json"""
import json
import os
import sys
from pathlib import Path

# 项目根目录（打包后 exe 所在目录，开发时为 main.py 所在目录）
if getattr(sys, 'frozen', False):
    ROOT_DIR = Path(sys.executable).resolve().parent
else:
    ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config.json"
PHOTO_DIR = ROOT_DIR / "Photo"

# 默认配置
DEFAULT_CONFIG = {
    "minecraft_dir": "",          # MC根目录（versions所在目录）
    "java_path": "",               # java.exe 路径
    "selected_version": "",        # 当前选中的版本
    "username": "",                # 当前玩家名
    "uuid": "",                    # 当前UUID
    "token": "",                   # 登录令牌
    "login_type": "offline",      # offline / microsoft
    "theme_mode": "auto",          # light / dark / auto
    "theme_color": "#009faa",     # 全局强调色
    "background_image": "",       # 自定义背景图路径
    "download_source": "mojang",   # mojang / bbmcl
    "download_dir": "",            # 下载目录
    "remember_account": True,
    "max_memory": 4096,            # 最大内存 MB
    "show_console": False,         # 是否显示黑色控制台窗口
}


class Config:
    """配置单例：读写 config.json"""

    def __init__(self):
        self.data = dict(DEFAULT_CONFIG)
        self.load()
        # 启动即创建 Photo 文件夹
        PHOTO_DIR.mkdir(parents=True, exist_ok=True)

    def load(self):
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self.data.update(saved)
            except Exception:
                pass

    def save(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Config] 保存失败: {e}")

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()

    # 便捷属性
    @property
    def minecraft_dir(self) -> str:
        return self.data.get("minecraft_dir", "")

    @minecraft_dir.setter
    def minecraft_dir(self, v: str):
        self.data["minecraft_dir"] = v
        self.save()

    @property
    def java_path(self) -> str:
        return self.data.get("java_path", "")

    @java_path.setter
    def java_path(self, v: str):
        self.data["java_path"] = v
        self.save()

    @property
    def photo_dir(self) -> Path:
        return PHOTO_DIR


# 全局单例
cfg = Config()
