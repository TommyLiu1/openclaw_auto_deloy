# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置：生成可执行文件，用户双击即可运行。
# 打包命令（在项目根目录）: pyinstaller openclaw_deploy.spec

import os
import sys

block_cipher = None
# 项目根目录，便于解析 openclaw_deploy 包
spec_dir = os.path.dirname(os.path.abspath(SPEC))

# 单文件 exe，控制台模式便于用户双击后看到输出与错误
a = Analysis(
    ['openclaw_deploy/__main__.py'],
    pathex=[spec_dir],
    binaries=[],
    datas=[],
    hiddenimports=[
        'openclaw_deploy',
        'openclaw_deploy.cli',
        'openclaw_deploy.license',
        'openclaw_deploy.deploy',
        'openclaw_deploy.machine_id',
        'openclaw_deploy.logger',
        'openclaw_deploy.channels_config',
        'openclaw_deploy.docker_installer',
        'loguru',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='openclaw-deploy',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,   # 保持控制台，用户双击可见输出
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
