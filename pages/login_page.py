"""平台登录页操作封装。

定位器依据：2026-10-23 实测 qa-platform.example.com 登录页 DOM
（输入框 placeholder 为「请输入用户名」「请输入密码」；
主按钮文本「登录」，另有「使用飞书登录」，故用 exact=True 精确匹配避免 strict mode 冲突）。
"""
from playwright.sync_api import Page, expect


def click_login_button(page: Page):
    """点击主登录按钮。

    注意：页面同时存在「登录」与「使用飞书登录」两个按钮，
    必须用 exact=True 精确匹配，否则 Playwright strict mode 会报冲突。
    """
    page.get_by_role("button", name="登录", exact=True).click()


def platform_login(page: Page, base_url: str, username: str, password: str):
    """登录 QA 平台，成功后停在项目列表页。"""
    page.goto(f"{base_url}/login", wait_until="domcontentloaded")
    page.wait_for_timeout(1000)

    page.get_by_placeholder("请输入用户名").fill(username)
    page.get_by_placeholder("请输入密码").fill(password)
    click_login_button(page)

    # 等待跳离登录页
    page.wait_for_url(lambda url: "/login" not in url, timeout=30000)
    page.wait_for_timeout(1500)

    # 演示环境提示弹窗：数据会被定期重置，属预期行为
    dismiss_demo_dialog(page)
    page.wait_for_timeout(1000)


def dismiss_demo_dialog(page: Page) -> bool:
    """关闭「演示环境」重置提示（若出现）。返回是否点到了按钮。"""
    for label in ["知道了", "确定", "我知道了"]:
        btn = page.locator(f'.el-dialog button:has-text("{label}")')
        if btn.count() > 0:
            try:
                btn.first.click(timeout=3000)
                page.wait_for_timeout(1200)
                return True
            except Exception:
                pass
    return False


def assert_login_success(page: Page):
    """断言登录成功：停留在项目列表页且核心操作入口可见。"""
    expect(page.get_by_text("项目列表").first).to_be_visible(timeout=15000)
    expect(page.get_by_role("button", name="创建项目").first).to_be_visible()


def assert_login_failed(page: Page):
    """断言登录失败：仍在登录页且出现错误提示。"""
    assert "/projects" not in page.url, "登录失败却跳转到了项目列表"
    expect(page.get_by_placeholder("请输入用户名")).to_be_visible(timeout=10000)