# -*- coding: utf-8 -*-
"""
使用 PyInstaller 打包工具端为可执行文件，用户双击即可运行（无需安装 Python）。
用法（在项目根目录执行）:
  pip install pyinstaller
  python build_exe.py
输出在 dist/openclaw-deploy（或 dist/openclaw-deploy.exe）。
"""
import subprocess
import sys
from pathlib import Path

def main():
    root = Path(__file__).resolve().parent
    spec = root / "openclaw_deploy.spec"
    if not spec.exists():
        print(f"未找到 {spec}", file=sys.stderr)
        return 1
    r = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", str(spec)],
        cwd=root,
    )
    if r.returncode != 0:
        print("打包失败", file=sys.stderr)
        return r.returncode
    exe_name = "openclaw-deploy.exe" if sys.platform == "win32" else "openclaw-deploy"
    print(f"打包完成，可执行文件: dist/{exe_name}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
