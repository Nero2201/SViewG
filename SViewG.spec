# -*- mode: python ; coding: utf-8 -*-
# Run: pyinstaller SViewG.spec
import os, sys

_icon = (
    'icon.icns' if sys.platform == 'darwin'  and os.path.exists('icon.icns') else
    'icon.ico'  if sys.platform == 'win32'   and os.path.exists('icon.ico')  else
    None
)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('lang', 'lang')],
    hiddenimports=[
        'PyQt6.QtSvg',
        'PyQt6.QtSvgWidgets',
        'PyQt6.sip',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SViewG',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SViewG',
)

app = BUNDLE(
    coll,
    name='SViewG.app',
    icon=_icon,
    bundle_identifier='com.sviewg.app',
    info_plist={
        'NSHighResolutionCapable': True,
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleName': 'SViewG',
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'SVG Image',
                'CFBundleTypeRole': 'Viewer',
                'LSHandlerRank': 'Alternate',
                'LSItemContentTypes': ['public.svg-image'],
                'CFBundleTypeExtensions': ['svg', 'svgz'],
            }
        ],
        'UTImportedTypeDeclarations': [
            {
                'UTTypeIdentifier': 'public.svg-image',
                'UTTypeDescription': 'SVG Image',
                'UTTypeConformsTo': ['public.xml', 'public.image'],
                'UTTypeTagSpecification': {
                    'public.filename-extension': ['svg', 'svgz'],
                    'public.mime-type': 'image/svg+xml',
                },
            }
        ],
    },
)
