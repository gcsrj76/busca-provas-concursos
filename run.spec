# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    # Adicionamos a pasta 'views' para que todas as interfaces (.py) sejam copiadas para dentro do executável
    datas=[('views', 'views')],
    # Forçamos o PyInstaller a carregar os módulos ocultos que o script principal não importa diretamente
    hiddenimports=[
        'views.main_activity',
        'views.view_processar'
    ],
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
    name='run',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Mantém True para você conseguir ver os logs de erro no terminal do Linux se algo ocorrer
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)