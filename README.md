# InfinityLauncher

一个用 Python 随手搓出来的 Minecraft Java 版启动器。
技术栈：Python 3 + PyQt6 + PyQt-Fluent-Widgets + minecraft-launcher-lib。

## 作者的话

大家好，我是 JunsongJS，这个小项目是我随手搓出来的，比较小，是一个 Minecraft Java 启动器，只不过使用 Python 做的。我真的非常热爱 Minecraft，严格说是它带我走进了编程，但我还在读书，没有太多多余精力编码，况且我的 Coding 能力也不强，所以不喜勿喷。这份启动器源码在我这里已经到头了，所以我想把它交给社区，看有没有有缘人能继续维护下去。OVO

## 功能

- 离线登录
- 微软账号登录（设备码 Device Code 流程，自动走 XBL → XSTS → Minecraft 认证）
- 扫描本地已安装的游戏版本
- 下载游戏版本（支持 Mojang 官方源 / BMCLAPI 镜像源）
- 支持安装 Forge / Fabric
- 一键启动游戏，自动处理 natives、主类等版本差异，强制版本隔离
- 可设置 Java 路径、内存大小、下载目录、主题等

## 运行方法

1. 安装 Python 3.10 及以上版本；
2. 在项目目录下安装依赖：

   ```
   pip install -r requirements.txt
   ```

3. 运行启动器：

   ```
   python main.py
   ```

   Windows 下也可以直接双击 `启动.bat`。

## 目录结构

```
InfinityLauncher/
├── main.py              # 程序入口
├── 启动.bat             # Windows 一键启动
├── requirements.txt     # 依赖列表
├── lauuncher.ico        # 程序图标
├── core/                # 核心逻辑
│   ├── auth.py          # 登录（离线 / 微软）
│   ├── config.py        # 配置管理（config.json）
│   ├── downloader.py    # 版本下载（Mojang / BMCLAPI）
│   ├── launcher.py      # 游戏启动
│   └── version_scanner.py  # 本地版本扫描
└── ui/                  # 界面
    ├── main_window.py   # 主窗口
    ├── dialogs.py       # 弹窗
    └── pages/           # 各页面（首页 / 登录 / 下载 / 设置）
```

## 给接手维护的人

- 运行时会在程序目录自动生成 `config.json`（保存本地配置和登录令牌）和 `Photo` 文件夹，这两个不会被上传；
- 下载镜像使用的是 BMCLAPI（bangbang93），感谢相关作者；
- 欢迎提 Issue 和 Pull Request。

## 开源协议

本项目基于 [MIT License](LICENSE) 开源，任何人都可以自由使用、修改和分发，但需要保留原版权声明。
