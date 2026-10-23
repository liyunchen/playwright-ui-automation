"""演示图集采集脚本（一次性工具，不参与 pytest 收集）。

用途：登录 qa-platform.example.com 后，按模块逐一截图，输出到 demo_screenshots/，
      供简历 / 面试展示使用。

用法：
    python scripts/capture_demo_shots.py

依赖：复用 pages/ 层的 Page Object，保证截图路径与自动化用例走同一套定位器，
      避免"截图能过、用例挂掉"的两套逻辑。
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

from pages.login_page import dismiss_demo_dialog
from pages.project_page import goto_projects, open_project, goto_module
# 复用 conftest 的零依赖 .env 加载器，保证与自动化用例读取配置的口径完全一致
from conftest import load_dotenv

load_dotenv()

BASE_URL = os.getenv("QA_URL", "https://qa-platform.example.com").rstrip("/")
USERNAME = os.getenv("QA_USERNAME", "admin")
PASSWORD = os.getenv("qa_password", "")
PROJECT_CODE = os.getenv("QA_PROJECT_CODE", "qa_demo")

OUT_DIR = ROOT / "demo_screenshots"
OUT_DIR.mkdir(exist_ok=True)

# (序号, 模块名, 截图文件名, 截图后额外操作)
SHOTS = [
    ("01", "登录页", "01_登录页.png", None),
    ("02", "项目列表", "02_项目列表.png", None),
    ("03", "项目工作台", "03_项目工作台.png", None),
    ("04", "手工用例", "04_手工用例.png", None),
    ("05", "接口管理", "05_接口管理.png", None),
    ("06", "自动化用例", "06_自动化用例.png", None),
    ("07", "测试任务", "07_测试任务.png", None),
    ("08", "测试报告", "08_测试报告.png", None),
    ("09", "数据管理", "09_数据管理.png", None),
    ("10", "测试环境", "10_测试环境.png", None),
]


def shoot(page, filename: str, full_page: bool = False):
    """截图并落盘。"""
    page.wait_for_timeout(1200)
    path = OUT_DIR / filename
    page.screenshot(path=str(path), full_page=full_page)
    size = path.stat().st_size
    print(f"  [OK] {filename}  ({size // 1024} KB)")


def main():
    if not PASSWORD:
        print("缺少 .env 中的 qa_password，无法采集")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1600, "height": 900},
            device_scale_factor=2,  # 2x 缩放，简历里放大多清晰
            locale="zh-CN",
        )
        page = ctx.new_page()

        print("→ 登录平台 ...")
        page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        shoot(page, "01_登录页.png")

        page.get_by_placeholder("请输入用户名").fill(USERNAME)
        page.get_by_placeholder("请输入密码").fill(PASSWORD)
        page.get_by_role("button", name="登录", exact=True).click()
        page.wait_for_url(lambda u: "/login" not in u, timeout=30000)
        page.wait_for_timeout(2500)
        dismiss_demo_dialog(page)

        print("→ 采集模块页面 ...")
        goto_projects(page, BASE_URL)
        shoot(page, "02_项目列表.png")

        open_project(page, BASE_URL, PROJECT_CODE)

        for _, module, filename, _ in SHOTS[2:]:
            goto_module(page, BASE_URL, PROJECT_CODE, module)
            shoot(page, filename)

        ctx.close()
        browser.close()

    print(f"\n完成，共 {len(SHOTS)} 张 → {OUT_DIR}")


if __name__ == "__main__":
    main()