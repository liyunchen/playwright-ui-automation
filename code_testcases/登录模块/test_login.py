"""登录模块 UI 自动化用例。

被测对象：QA 自动化测试平台（地址见 config/env_config.yaml）
覆盖：正常登录、错误口令、登录态复用后的直接访问
"""

import os

import allure
import pytest
from playwright.sync_api import expect

from pages.login_page import (
    platform_login,
    click_login_button,
    dismiss_demo_dialog,
    assert_login_success,
    assert_login_failed,
)


@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.login
@pytest.mark.smoke
def test_login_with_valid_credentials(page, base_url, platform_username, platform_password):
    """正确账号密码可正常登录并进入项目列表页"""

    with allure.step("1. 打开登录页并校验关键元素"):
        page.goto(f"{base_url}/login", wait_until="domcontentloaded")
        expect(page.get_by_placeholder("请输入用户名")).to_be_visible(timeout=15000)
        expect(page.get_by_placeholder("请输入密码")).to_be_visible()
        expect(page.get_by_role("button", name="登录", exact=True)).to_be_visible()

    with allure.step("2. 输入账号密码并提交"):
        platform_login(page, base_url, platform_username, platform_password)

    with allure.step("3. 校验登录成功并跳转项目列表"):
        assert_login_success(page)
        assert "/projects" in page.url, f"未跳转至项目列表页，当前: {page.url}"


@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.login
def test_login_with_wrong_password_shows_error(page, base_url, platform_username):
    """错误口令应被拒绝：不跳转项目列表、不下发token

    实现说明：失败响应（HTTP 401）会触发页面跳转，导致 Playwright 无法再读取
    响应体（Response body is not available for a response that was navigated away from）。
    因此这里不依赖响应体，改为断言「状态码为 401 + 未跳转 + 未拿到 token」
    这三个可稳定观测的事实。
    """

    with allure.step("1. 打开登录页并监听登录接口状态码"):
        page.goto(f"{base_url}/login", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)

        statuses = []

        def handle(response):
            if "auth/login" in response.url:
                statuses.append(response.status)

        page.on("response", handle)

    with allure.step("2. 用错误口令发起登录"):
        page.get_by_placeholder("请输入用户名").fill(platform_username)
        # 故意用错的口令，值本身无意义但仍从环境变量取，避免把测试数据写死在代码里
        wrong_password = os.environ.get("QA_WRONG_PASSWORD", "wrong_password_for_test")
        page.get_by_placeholder("请输入密码").fill(wrong_password)
        click_login_button(page)
        page.wait_for_timeout(5000)
        page.remove_listener("response", handle)
        print(f"登录接口状态码: {statuses}")

    with allure.step("3. 校验登录被拒绝"):
        assert statuses, "未发出登录请求"
        assert statuses[0] == 401, f"错误口令应返回 401，实际 {statuses[0]}"
        assert_login_failed(page)

        # 确认本地存储中没有被写入有效 token
        token = page.evaluate("() => localStorage.getItem('access_token')")
        assert not token, "登录失败时不应写入 access_token"


@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.login
def test_login_redirects_unauthenticated_user(page, base_url):
    """未登录直接访问项目列表应被重定向回登录页"""

    with allure.step("1. 未登录状态访问受保护页面"):
        page.goto(f"{base_url}/projects", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)

    with allure.step("2. 校验被重定向到登录页"):
        assert "/login" in page.url, f"未重定向到登录页，当前: {page.url}"
        expect(page.get_by_placeholder("请输入用户名")).to_be_visible(timeout=10000)


@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.login
def test_login_page_has_feishu_entry(page, base_url):
    """登录页应提供飞书登录入口"""

    with allure.step("1. 打开登录页"):
        page.goto(f"{base_url}/login", wait_until="domcontentloaded")
        page.wait_for_timeout(1500)

    with allure.step("2. 校验飞书登录入口存在"):
        expect(page.get_by_text("使用飞书登录").first).to_be_visible(timeout=10000)


@allure.severity(allure.severity_level.MINOR)
@pytest.mark.login
def test_demo_environment_notice_is_dismissable(page, base_url, platform_username, platform_password):
    """演示环境数据重置提示可正常关闭，不阻塞后续操作"""

    with allure.step("1. 登录并观察演示环境提示"):
        platform_login(page, base_url, platform_username, platform_password)

    with allure.step("2. 确认弹窗已关闭且可继续操作"):
        dialog_gone = True
        if page.locator(".el-dialog").count() > 0:
            dialog_gone = dismiss_demo_dialog(page)
        assert dialog_gone or page.locator(".el-dialog:visible").count() == 0, \
            "演示环境提示弹窗未关闭，阻塞了后续操作"

        # 关闭后应能正常看到项目列表
        expect(page.get_by_text("项目列表").first).to_be_visible(timeout=10000)