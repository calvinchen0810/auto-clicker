# server.spec
# PyInstaller 打包設定
# 執行：pyinstaller server.spec

import os
from PyInstaller.utils.hooks import collect_data_files

ROOT = os.path.abspath(SPECPATH)

hidden_imports = [
    "uvicorn.logging",
    "uvicorn.loops", "uvicorn.loops.auto", "uvicorn.loops.asyncio",
    "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan", "uvicorn.lifespan.on",
    "fastapi", "starlette", "starlette.routing",
    "starlette.middleware", "starlette.middleware.cors",
    "anyio", "anyio._backends._asyncio",
    "serial", "serial.tools", "serial.tools.list_ports",
    "serial.tools.list_ports_windows",
    "email.mime.text", "email.mime.multipart",
    "winreg",
]

datas = []
datas += collect_data_files("uvicorn")
datas += collect_data_files("fastapi")
datas += collect_data_files("starlette")
# 打包 index.html
datas += [(os.path.join(ROOT, "static"), "static")]

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[os.path.join(ROOT, "rthook_asyncio.py")],
    excludes=["tkinter","matplotlib","numpy","scipy","pandas","PIL","pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name        = "ServoServer",
    debug       = False,
    strip       = False,
    upx         = True,
    console     = True,          # 保留 console（用來顯示狀態）
    icon        = os.path.join(ROOT, "icon.ico"),
)
