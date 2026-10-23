"""演示素材脱敏脚本（公开发布前必跑）。

处理 grep 查不出来的敏感信息——它们只存在于**图像像素**里：

1.侧边栏底部的登录账号手机号（副标题行，11 位数字）
2. 登录页输入框里的用户名（公开后等于泄露账号的一半凭据）

做法：对已定位的像素区域做马赛克，缩到极小尺寸再放大 = 不可逆。

坐标基准（两种分辨率各自一套，按图片实际宽度自动换算）：
- 截图 3200×1800（device_scale_factor=2）
    手机号  x=110~216, y=1739~1764
- 视频 1280×720（Playwright 默认录制尺寸）
    手机号  x=39~104, y=687~701
    用户名  x=37~120, y=676~688

用法：
    python scripts/redact_demo_assets.py# 仅截图
    python scripts/redact_demo_assets.py --videos   # 截图 + 全部视频
"""
import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHOTS_DIR = ROOT / "demo_screenshots"
VIDEOS_DIR = ROOT / "demo_videos"
DEMO_VIDEO = ROOT / "demo_assets" / "UI自动化演示精选.mp4"

# 各基准分辨率下的敏感区域（左, 上, 右, 下）
# 视频坐标经刻度标定法测得（1280×720 录屏，左下角用户信息区）
# 区域刻意比文字略大，宁可多遮一点也不留可辨认残影
REGIONS = {
    3200: [(105, 1734, 225, 1770)],                      # 截图：手机号副标题
    1280: [
        (34, 692, 112, 706),   # 手机号副标题
        (34, 668, 128, 692),   # 用户名
    ],
}


def _mosaic(im, box):
    """对指定区域做不可逆马赛克。"""
    from PIL import Image
    x0, y0, x1, y1 = box
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(im.width, x1), min(im.height, y1)
    if x1 <= x0 or y1 <= y0:
        return
    region = im.crop((x0, y0, x1, y1)).resize((4, 2), Image.NEAREST)
    im.paste(region.resize((x1 - x0, y1 - y0), Image.NEAREST), (x0, y0))


def redact_image(path):
    """对单张图片按其宽度匹配最近的坐标基准并脱敏。"""
    from PIL import Image
    im = Image.open(path).convert("RGB")

    # 选最接近的基准分辨率，按比例缩放坐标
    base_w = min(REGIONS.keys(), key=lambda b: abs(b - im.width))
    scale = im.width / base_w
    for box in REGIONS[base_w]:
        _mosaic(im, tuple(int(v * scale) for v in box))

    im.save(path)
    return base_w


def redact_videos():
    """视频脱敏：用 ffmpeg 内置 delogo 滤镜单次处理。

    为什么不用「抽帧 → 逐帧处理 → 重组」：
    该方案会产生上千个临时帧文件，删除时易触发系统安全拦截，且慢 10 倍以上。
    delogo 是ffmpeg 内置的不可逆插值模糊，一步完成且无中间文件。

    delogo 会对指定矩形做周边像素插值填充，人眼与OCR 均无法还原原文。
    """
    try:
        import imageio_ffmpeg
    except ImportError:
        print("需要 imageio-ffmpeg：pip install imageio-ffmpeg")
        return

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    work = ROOT / ".redact_work"
    work.mkdir(exist_ok=True)

    targets = sorted(glob.glob(str(VIDEOS_DIR / "*.webm"))) \
        + sorted(glob.glob(str(VIDEOS_DIR / "*.mp4")))
    if DEMO_VIDEO.exists():
        targets.append(str(DEMO_VIDEO))

    # 基准 1280×720 下的敏感区域（左, 上, 宽, 高），delogo 用 x/y/w/h
    boxes = REGIONS[1280]
    filters = []
    for x0, y0, x1, y1 in boxes:
        filters.append(f"delogo=x={x0}:y={y0}:w={x1 - x0}:h={y1 - y0}:show=0")

    done = skip = 0
    for src in targets:
        name = Path(src).stem
        tmp = work / f"{name}_clean.mp4"
        vf = ",".join(filters)

        r = subprocess.run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                            "-i", src, "-vf", vf,
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
                            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                            "-an", str(tmp)], capture_output=True)
        if r.returncode != 0 or not tmp.exists():
            print(f"  [FAIL] {name}: {r.stderr.decode(errors='ignore')[:120]}")
            skip += 1
            continue

        # 统一落地为 mp4（webm 是脱敏前原片，不应留在对外仓库）
        final = Path(src).with_suffix(".mp4")
        Path(src).unlink(missing_ok=True)
        tmp.replace(final)
        done += 1
        print(f"  [OK] {final.name}", flush=True)

    try:
        work.rmdir()
    except OSError:
        pass
    print(f"视频脱敏完成：{done} 个已处理，{skip} 个失败/跳过")


def main():
    shots = sorted(glob.glob(str(SHOTS_DIR / "*.png")))
    print(f"→ 处理 {len(shots)} 张截图 ...")
    for p in shots:
        base = redact_image(p)
        print(f"  [OK] {Path(p).name} (基准 {base}px)")

    if "--videos" in sys.argv:
        print("→ 处理视频（耗时较长，请耐心等待）...")
        redact_videos()
    else:
        print("提示：加 --videos 参数可一并脱敏视频")


if __name__ == "__main__":
    main()