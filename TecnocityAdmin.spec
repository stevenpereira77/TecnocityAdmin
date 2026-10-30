# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for a Windows onedir distribution."""
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

datas = [
    ("assets/app.qss", "assets"),
    ("LICENSE", "."),
    ("docs/THIRD_PARTY_LICENSES.md", "docs"),
]
datas += collect_data_files("google_auth_oauthlib")

hiddenimports = [
    "google.auth.transport.requests",
    "google.oauth2.credentials",
    "google_auth_oauthlib.flow",
    "googleapiclient.discovery",
    "googleapiclient.http",
]

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6.QtCharts", "PySide6.QtGraphs"],
    noarchive=False,
)
pyz = PYZ(a.pure, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TecnocityAdmin",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="TecnocityAdmin",
)
