# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


ttkbootstrap_datas = collect_data_files('ttkbootstrap')
ttkbootstrap_hiddenimports = collect_submodules('ttkbootstrap')


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=ttkbootstrap_datas,
    hiddenimports=ttkbootstrap_hiddenimports,
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
    name='CurlRunner',
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
