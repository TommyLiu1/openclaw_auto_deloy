# -*- coding: utf-8 -*-
"""支持 python -m openclaw_deploy 与 PyInstaller 打包入口。用户双击 exe 即可运行。"""
import sys
import traceback

def _should_pause_before_exit():
    """打包 exe 时退出前是否暂停，避免双击运行窗口闪退。"""
    if not getattr(sys, "frozen", False):
        return False
    # 非交互式（如双击新建的控制台）或运行出错时暂停，便于用户看到输出
    # 注意：Windows 双击 exe 时新建控制台可能仍被识别为 TTY，故打包后统一在退出前暂停
    return True

def _pause_before_exit():
    try:
        input("\n按回车键退出...")
    except Exception:
        pass

if __name__ == "__main__":
    code = 0
    try:
        # 使用绝对导入，避免 PyInstaller 打包后相对导入报错 "no known parent package"
        from openclaw_deploy.cli import main
        code = main()
    except Exception as e:
        code = 1
        print("\n运行出错:", e, file=sys.stderr)
        traceback.print_exc()
    # 打包 exe 时退出前暂停，避免双击运行窗口闪退
    if _should_pause_before_exit():
        _pause_before_exit()
    sys.exit(code)
