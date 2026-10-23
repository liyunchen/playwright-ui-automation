"""演示视频合成脚本（一次性工具）。

把 demo_videos/ 下按用例拆分的录屏，剪成一条带章节标题卡的精选集，
输出 demo_assets/UI自动化演示精选.mp4，供简历 / 面试播放。

做法：
1. 用 Playwright 渲染 HTML 标题卡 → PNG（避免依赖 ffmpeg 的 drawtext 字体问题）
2. 每段标题卡 + 视频片段统一转成 mp4（h264 / yuv420p / 1280x720 / 25fps）
3. concat 拼成整片

用法：python scripts/build_demo_video.py
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from conftest import load_dotenv
load_dotenv()

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
VID_DIR = ROOT / "demo_videos"
WORK = ROOT / ".video_build"
OUT = ROOT / "demo_assets" / "UI自动化演示精选.mp4"

W, H, FPS = 1280, 720, 25

# (标题, 副标题, 源视频文件, 保留时长秒)
CHAPTERS = [
    ("登录模块", "正确 / 错误密码 / 未授权重定向 / 演示环境提示", "test_login_with_valid_credentials.webm", 8),
    ("项目工作台", "统计卡片 · 资产入口 · 近 7 天执行趋势", "test_enter_project_and_load_dashboard.webm", 10),
    ("项目列表搜索", "按项目代码检索 · 空结果态断言", "test_project_search_by_code.webm", 9),
    ("手工用例管理", "列表加载 · 关键字检索 · 新增用例", "test_manual_case_search_by_keyword.webm", 11),
    ("接口管理目录树", "342 个接口定义 · 23 个分类 · 结构接口断言", "test_api_tree_api_returns_structure.webm", 11),
    ("接口搜索", "输入关键字实时过滤 · 清空后恢复全量", "test_api_search_input_works.webm", 11),
    ("UI + 接口 + 数据 三重校验", "捕获 /summary 响应并断言真实业务数据", "test_project_summary_api_returns_data.webm", 10),
    ("多模块导航回归", "工作台 / 用例 / 接口 / 任务 / 计划 一次跑通", "test_navigate_between_modules.webm", 14),
    ("数据管理", "工厂 · 快照 · 数据池 · 清理", "test_data_management_page_loads.webm", 10),
    ("测试环境", "环境列表 · 配置接口校验", "test_environments_api_returns_config.webm", 10),
]

CARD_HTML = """<!doctype html><html><head><meta charset="utf-8">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ width:{w}px; height:{h}px; display:flex; align-items:center; justify-content:center;
    background:linear-gradient(135deg,#0f172a 0%,#1e293b 55%,#0b1220 100%);
    font-family:"Microsoft YaHei","PingFang SC",sans-serif; color:#e2e8f0; }}
  .box {{ text-align:center; padding:0 90px; }}
  .no {{ font-size:20px; letter-spacing:6px; color:#38bdf8; margin-bottom:22px; font-weight:600; }}
  .t {{ font-size:56px; font-weight:700; margin-bottom:20px; line-height:1.25; }}
  .bar {{ width:96px; height:4px; background:#38bdf8; margin:0 auto 22px; border-radius:2px; }}
  .s {{ font-size:25px; color:#94a3b8; line-height:1.6; }}
  .tag {{ position:absolute; bottom:52px; left:0; right:0; text-align:center;
    font-size:18px; color:#64748b; letter-spacing:2px; }}
</style></head><body>
  <div class="box">
    <div class="no">{no}</div>
    <div class="t">{title}</div>
    <div class="bar"></div>
    <div class="s">{sub}</div>
  </div>
  <div class="tag">Playwright + Pytest · qa-platform.example.com 自动化测试平台</div>
</body></html>"""


def make_card(idx, title, sub, out_png):
    """渲染章节标题卡为 PNG。"""
    from playwright.sync_api import sync_playwright
    html = CARD_HTML.format(w=W, h=H, no=f"CHAPTER {idx:02d}", title=title, sub=sub)
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_context(viewport={"width": W, "height": H},
                           device_scale_factor=2).new_page()
        pg.set_content(html, wait_until="load")
        pg.wait_for_timeout(600)
        pg.screenshot(path=str(out_png))
        b.close()


def to_mp4(src, dst, seconds, is_image=False):
    """统一规格转码（时长截断到 seconds）。

    图片输入必须加 -loop 1 -framerate，否则 ffmpeg 认为只有 1 帧、
    产出的片段时长为 0，concat 时会被判为无有效流。
    """
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error"]
    if is_image:
        cmd += ["-loop", "1", "-framerate", str(FPS)]
    cmd += [
        "-i", str(src), "-t", str(seconds),
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
               f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps={FPS}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-an", str(dst),
    ]
    subprocess.run(cmd, check=True)


def main():
    WORK.mkdir(exist_ok=True)
    OUT.parent.mkdir(exist_ok=True)

    parts = []
    # 片头
    head = WORK / "head.mp4"
    make_card(0, "UI 自动化测试演示", "基于 Playwright + Pytest 的接口 / 数据 / 任务编排验证", WORK / "head.png")
    to_mp4(WORK / "head.png", head, 4, is_image=True)
    parts.append(head)

    for i, (title, sub, fname, secs) in enumerate(CHAPTERS, start=1):
        src = VID_DIR / fname
        if not src.exists():
            print(f"  [SKIP] 缺失 {fname}")
            continue
        card_png = WORK / f"card{i}.png"
        card_mp4 = WORK / f"card{i}.mp4"
        clip_mp4 = WORK / f"clip{i}.mp4"
        make_card(i, title, sub, card_png)
        to_mp4(card_png, card_mp4, 2.5, is_image=True)
        to_mp4(src, clip_mp4, secs)
        parts.extend([card_mp4, clip_mp4])
        print(f"  [OK] {i:02d} {title}  ({fname} 取 {secs}s)")

    # 校验每段都有有效时长，避免 concat 静默产出空文件
    for p in parts:
        if p.stat().st_size < 2048:
            raise RuntimeError(f"片段异常（{p.stat().st_size} 字节）：{p.name}")

    lst = WORK / "list.txt"
    # 注意：concat 清单必须用 LF 换行，且在 Windows 上正斜杠绝对路径会被
    # 当成协议分隔符导致读不到流，因此切到工作目录后只写裸文件名。
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts),
                   encoding="utf-8", newline="\n")
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "concat", "-safe", "0", "-i", lst.name,
                    "-c", "copy", str(OUT)], check=True, cwd=str(WORK))

    size_mb = OUT.stat().st_size / 1024 / 1024
    print(f"\n完成 → {OUT.name}  ({size_mb:.1f} MB, {len(parts)} 段)")


if __name__ == "__main__":
    main()