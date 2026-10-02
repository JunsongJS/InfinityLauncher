# -*- coding: utf-8 -*-
"""
InfinityLauncher - Minecraft Java Edition Launcher
Python 3.14 + PyQt6 + PyQt-Fluent-Widgets
"""
import sys
from pathlib import Path

# Windows 任务栏图标
if sys.platform == "win32":
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("InfinityLauncher.App")

# 把项目根目录加入 sys.path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from qfluentwidgets import FluentTranslator
from ui.main_window import MainWindow


def main():
    # High DPI
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("InfinityLauncher")

    # 应用图标
    icon_path = ROOT / "lauuncher.ico"
    if not icon_path.exists():
        icon_path = ROOT / "launcher.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Fluent 翻译
    translator = FluentTranslator()
    app.installTranslator(translator)

    # 创建并显示主窗口
    window = MainWindow()
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
