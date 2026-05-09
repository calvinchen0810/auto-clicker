"""
server/build.py
一鍵打包 ServoServer.exe

執行：python build.py [--clean]
輸出：dist/ServoServer.exe
"""

import sys, os, shutil, struct, subprocess, argparse

ROOT = os.path.dirname(os.path.abspath(__file__))


def gen_icon():
    """產生 .ico 圖示（不依賴 Pillow）"""
    size = 32
    fg   = (34, 197, 94, 255)   # 綠色
    bg   = (0,  0,   0,  0)     # 透明

    pixels = []
    cx = cy = size / 2
    r  = size / 2 - 2
    for y in range(size):
        for x in range(size):
            pixels.append(fg if ((x-cx)**2 + (y-cy)**2)**0.5 <= r else bg)

    def bmp():
        h = struct.pack("<IiiHHIIiiII", 40, size, size*2, 1, 32, 0, size*size*4, 0,0,0,0)
        rows = b"".join(
            struct.pack("BBBB", p[2], p[1], p[0], p[3])
            for y in range(size-1,-1,-1)
            for p in [pixels[y*size+x] for x in range(size)]
        )
        mask = b"\x00" * ((size+31)//32*4 * size)
        return h + rows + mask

    bmp_data = bmp()
    ico_hdr  = struct.pack("<HHH", 0, 1, 1)
    entry    = struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(bmp_data), 6+16)
    path     = os.path.join(ROOT, "icon.ico")
    with open(path, "wb") as f:
        f.write(ico_hdr + entry + bmp_data)
    print(f"  ✅ icon.ico 產生：{path}")


def clean():
    for d in ["build", "dist", "__pycache__"]:
        p = os.path.join(ROOT, d)
        if os.path.exists(p):
            shutil.rmtree(p); print(f"  🗑  清除：{p}")
    for dirpath, dirnames, _ in os.walk(ROOT):
        for d in list(dirnames):
            if d == "__pycache__":
                shutil.rmtree(os.path.join(dirpath, d))


def build():
    spec = os.path.join(ROOT, "server.spec")
    r = subprocess.run(
        [sys.executable, "-m", "PyInstaller", spec, "--noconfirm", "--log-level=WARN"],
        cwd=ROOT,
    )
    return r.returncode == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()

    print("=" * 44)
    print("  ServoServer — PyInstaller 打包")
    print("=" * 44)

    if sys.platform != "win32":
        print("\n⚠️  非 Windows 環境，打包出的不是 .exe")

    print("\n[1/3] 產生圖示…"); gen_icon()
    if args.clean:
        print("\n[2/3] 清除舊檔…"); clean()
    else:
        print("\n[2/3] 跳過清除（--clean 可強制清除）")
    print("\n[3/3] 執行 PyInstaller…")
    if build():
        exe = os.path.join(ROOT, "dist", "ServoServer.exe")
        mb  = os.path.getsize(exe) / 1024 / 1024 if os.path.exists(exe) else 0
        print(f"\n  ✅ 完成！輸出：{exe}  ({mb:.1f} MB)")
    else:
        print("\n  ❌ 打包失敗")
        sys.exit(1)
