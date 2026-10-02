# -*- coding: utf-8 -*-
"""
登录模块：
  1. 离线登录：直接生成随机 UUID，用户名由用户输入
  2. 微软登录：使用 Azure Device Code Flow
     - 请求设备码 -> 弹出浏览器并自动复制识别码 -> 轮询获取令牌
     - 拿到 access_token 后走 XBL -> XSTS -> Minecraft 认证 -> 获取玩家档案
"""
import json
import secrets
import threading
import time
import uuid as uuidlib

import requests
from PyQt6.QtCore import QObject, pyqtSignal

import minecraft_launcher_lib as mcl

from .config import cfg


# 微软 Live 旧版端点（兼容官方启动器 client_id 00000000402b5328）
AZURE_CLIENT_ID = "00000000402b5328"
DEVICE_CODE_URL = "https://login.live.com/oauth20_connect.srf"
TOKEN_URL = "https://login.live.com/oauth20_token.srf"
SCOPE = "XboxLive.signin offline_access"


def offline_login(username: str) -> dict:
    """离线登录：根据用户名生成离线 UUID"""
    # 离线 UUID 规范：md5("OfflinePlayer:" + username) 变体
    md5_input = f"OfflinePlayer:{username}".encode("utf-8")
    import hashlib
    h = hashlib.md5(md5_input).digest()
    b = bytearray(h)
    b[6] = (b[6] & 0x0F) | 0x30   # version 3
    b[8] = (b[8] & 0x3F) | 0x80   # variant
    offline_uuid = str(uuidlib.UUID(bytes=bytes(b)))

    cfg.set("login_type", "offline")
    cfg.set("username", username)
    cfg.set("uuid", offline_uuid)
    cfg.set("token", "0" * 16)
    return {"username": username, "uuid": offline_uuid, "token": "0" * 16}


class MicrosoftLoginWorker(QObject):
    """
    微软设备码登录流程（在后台线程跑）
    信号：
      show_code(user_code, verification_uri)  —— 拿到识别码，通知UI弹窗
      log(str)                                  —— 日志
      success(player_name, uuid, token)         —— 成功
      failed(str)                               —— 失败
      cancelled()                               —— 用户取消
    """
    show_code = pyqtSignal(str, str)
    log = pyqtSignal(str)
    success = pyqtSignal(str, str, str)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop = False

    def cancel(self):
        self._stop = True

    def run(self):
        try:
            self._device_code_flow()
        except Exception as e:
            self.failed.emit(f"微软登录失败: {e}")

    def _device_code_flow(self):
        # 1. 请求设备码
        self.log.emit("正在向微软请求设备码...")
        resp = requests.post(
            DEVICE_CODE_URL,
            data={
                "client_id": AZURE_CLIENT_ID,
                "scope": SCOPE,
                "response_type": "device_code",
            },
            timeout=15,
        )
        if resp.status_code != 200:
            self.failed.emit(f"请求设备码失败: {resp.status_code} {resp.text}")
            return
        data = resp.json()
        user_code = data["user_code"]
        device_code = data["device_code"]
        verification_uri = data["verification_uri"]
        interval = data.get("interval", 5)
        expires_in = data.get("expires_in", 900)

        self.log.emit(f"识别码: {user_code}")
        self.log.emit(f"请访问: {verification_uri}")
        # 通知 UI：弹出小窗显示识别码，并自动打开浏览器
        self.show_code.emit(user_code, verification_uri)

        # 2. 轮询 token
        deadline = time.time() + expires_in
        while time.time() < deadline:
            if self._stop:
                self.cancelled.emit()
                return
            time.sleep(interval)
            tr = requests.post(
                TOKEN_URL,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "client_id": AZURE_CLIENT_ID,
                    "device_code": device_code,
                },
                timeout=15,
            )
            tdata = tr.json()
            if "access_token" in tdata:
                access_token = tdata["access_token"]
                refresh_token = tdata.get("refresh_token", "")
                self.log.emit("微软账号认证成功，正在连接 Xbox Live...")
                break
            err = tdata.get("error", "")
            if err == "authorization_pending":
                continue
            elif err == "slow_down":
                interval += 5
                continue
            else:
                self.failed.emit(f"登录轮询出错: {tdata.get('error_description', err)}")
                return
        else:
            self.failed.emit("登录超时，请重试")
            return

        # 3. XBL -> XSTS -> Minecraft
        try:
            xbl = mcl.microsoft_account.authenticate_with_xbl(access_token)
            self.log.emit("Xbox Live 认证成功")
            xsts = mcl.microsoft_account.authenticate_with_xsts(xbl["Token"])
            self.log.emit("XSTS 认证成功")
            mc_auth = mcl.microsoft_account.authenticate_with_minecraft(
                xsts["DisplayClaims"]["xui"][0]["uhs"], xsts["Token"]
            )
            mc_token = mc_auth["access_token"]
            self.log.emit("Minecraft 服务认证成功")
            profile = mcl.microsoft_account.get_profile(mc_token)
            player_name = profile["name"]
            player_uuid = profile["id"]
            self.log.emit(f"欢迎，{player_name}!")
        except Exception as e:
            self.failed.emit(f"游戏账号认证失败: {e}")
            return

        # 保存到配置
        cfg.set("login_type", "microsoft")
        cfg.set("username", player_name)
        cfg.set("uuid", player_uuid)
        cfg.set("token", mc_token)
        if refresh_token:
            cfg.set("refresh_token", refresh_token)

        self.success.emit(player_name, player_uuid, mc_token)
