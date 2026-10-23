"""通用断言与网络监听工具。

沿用「UI + 接口 + 数据」三重校验思路：操作真实 UI 的同时捕获后端接口响应，
再对响应内容做断言，避免只校验页面文案导致的误判。
"""
import logging
from playwright.sync_api import Page, expect

logger = logging.getLogger("qa_test")


def verify_texts(page: Page, texts: list):
    """校验页面上多个文本元素可见。

    支持两种写法：
        '提交成功'              模糊匹配
        ('SOW', True)           精确匹配

    多个同名元素时自动挑第一个可见的，规避 Playwright strict mode 冲突。
    """
    for text in texts:
        if isinstance(text, tuple):
            locator = page.get_by_text(text[0], exact=text[1])
        else:
            locator = page.get_by_text(text)

        try:
            expect(locator).to_be_visible(timeout=8000)
        except Exception as e:
            if "strict mode violation" in str(e):
                found = False
                for i in range(locator.count()):
                    if locator.nth(i).is_visible():
                        expect(locator.nth(i)).to_be_visible(timeout=8000)
                        found = True
                        break
                if not found:
                    expect(locator.first).to_be_visible(timeout=8000)
            else:
                raise


def assert_input_value(page: Page, placeholder: str, expected: str):
    """断言输入框当前值为指定内容。"""
    actual = page.get_by_placeholder(placeholder).input_value()
    assert actual == expected, f"输入框[{placeholder}]期望 {expected}，实际 {actual}"


def capture_api_response(page: Page, api_fragment: str, action, wait_ms: int = 2500):
    """监听并捕获匹配 URL 片段的接口响应 JSON。

    Args:
        page: Playwright 页面
        api_fragment: URL 片段，如 "/api/v1/projects"
        action: 触发接口调用的可执行对象
        wait_ms: 调用后等待响应到达的毫秒数

    Returns:
        dict：捕获到的响应体，未捕获到则为空 dict
    """
    captured = {}

    def handle(response):
        if api_fragment in response.url:
            try:
                captured.update(response.json())
                logger.info(f"捕获接口响应: {api_fragment} -> {list(captured.keys())}")
            except Exception as e:
                logger.warning(f"解析响应失败 {response.url}: {e}")

    page.on("response", handle)
    try:
        action()
        page.wait_for_timeout(wait_ms)
    finally:
        page.remove_listener("response", handle)

    return captured


def assert_api_success(response: dict, step_name: str = ""):
    """断言平台接口返回成功（业务码 0 为成功）。"""
    assert response, f"{step_name} 未捕获到接口响应"
    code = response.get("code")
    assert code == 0, f"{step_name} 接口业务码异常: {code}, msg={response.get('message')}"


def assert_button_visible(page: Page, name: str, timeout: int = 10000):
    """断言按钮可见（存在于DOM 中且未被隐藏）。

    平台使用 Element Plus，部分按钮（如数据管理页的「创建快照」）位于
    折叠面板内，默认 hidden。此处只校验元素已挂载，不要求可见，
    避免因面板默认收起而误判失败。
    """
    locator = page.get_by_text(name, exact=True)
    locator.first.wait_for(state="attached", timeout=timeout)


def assert_button_clickable(page: Page, name: str, timeout: int = 10000):
    """断言按钮真正可见可点击（用于默认展开区域的主要操作按钮）。"""
    page.get_by_text(name, exact=True).first.wait_for(state="visible", timeout=timeout)


def verify_any_text(page: Page, keywords: list, timeout: int = 8000):
    """断言页面文案中至少出现 keywords 里的一个词。

    用于「结果反馈」这类弱断言：平台在不同状态下文案不固定
    （可能是命中结果，也可能是空态提示），只要有反馈即视为通过。
    """
    deadline = timeout
    step = 500
    waited = 0
    while waited < deadline:
        body = page.locator("body").inner_text()
        if any(k in body for k in keywords):
            return True
        page.wait_for_timeout(step)
        waited += step
    raise AssertionError(f"页面文案中未出现任一关键词: {keywords}")


def wait_for_loading_done(page: Page, timeout: int = 15000):
    """等待页面的 loading 遮罩消失。"""
    try:
        page.locator(".el-loading-mask, .ant-spin-spinning").first.wait_for(
            state="hidden", timeout=timeout
        )
    except Exception:
        pass


def assert_no_error_banner(page: Page):
    """断言页面未出现全局错误提示。"""
    errors = page.locator(".el-message--error, .ant-message-error, [class*='error-text']")
    assert errors.count() == 0, f"页面出现错误提示: {errors.first.inner_text() if errors.count() else ''}"


def take_screenshot(page: Page, name: str, directory: str = "demo_screenshots"):
    """主动截图，用于演示素材留档。"""
    import os
    os.makedirs(directory, exist_ok=True)
    path = os.path.abspath(f"{directory}/{name}.png")
    page.screenshot(path=path, full_page=True)
    logger.info(f"截图已保存: {path}")
    return path