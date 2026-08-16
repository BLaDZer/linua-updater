# -*- mode: python ; coding: utf-8 -*-

import os


base_dir = os.path.dirname(os.path.abspath(SPEC))

extra_binaries = []

aria2_name = "aria2c.exe" if os.name == "nt" else "aria2c"
aria2_bin = os.path.join(base_dir, "tools", aria2_name)
if os.path.exists(aria2_bin):
    extra_binaries.append((aria2_bin, "."))

sevenzip_names = ["7z.exe", "7z.dll"] if os.name == "nt" else ["7zz"]
for name in sevenzip_names:
    sevenzip_bin = os.path.join(base_dir, "tools", name)
    if os.path.exists(sevenzip_bin):
        extra_binaries.append((sevenzip_bin, "."))

a = Analysis(
    ['linua_updater/__main__.py'],
    pathex=[base_dir],
    binaries=extra_binaries,
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Linua-Updater',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)