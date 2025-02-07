# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('libiconv.dll', '.'),('libzbar-64.dll', '.'),('blue_circle.ico','.'), ('blue_circle.jpg', '.'), ('logo.jpg','.'), ('img_circle1.jpg','.'), ('img_circle2.jpg','.'), ('img_circle3.jpg','.'),('cvt.ui','.'), ('3Dmodel.jpg','.')],
    hiddenimports=['pyzbar', 'pyzbar.zbar_library'],
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
    name='Designed_by_Group7',
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
    icon='blue_circle.ico',
)
