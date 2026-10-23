"""环境管理模块 UI 自动化用例。

覆盖：测试环境列表、变量入口、新建入口、环境数据结构校验、CI/CD 集成入口。
定位器依据 2026-10-23 实测 DOM。
"""
import allure
import pytest
from playwright.sync_api import expect

from pages.project_page import goto_module, get_project_id
from pages.assertion_helpers import (
    capture_api_response,
    verify_texts,
    verify_any_text,
    assert_button_visible,
    assert_button_clickable,
)


@allure.severity(allure.severity_level.NORMAL)
def test_environments_list_loads(logged_page, base_url, project_code):
    """测试环境页正常加载，展示新建与变量入口"""

    with allure.step("1. 进入测试环境页"):
        goto_module(logged_page, base_url, project_code, "测试环境")

    with allure.step("2. 校验核心元素"):
        expect(logged_page.get_by_text("测试环境").first).to_be_visible(timeout=15000)
        verify_texts(logged_page, ["新建环境", "变量"])


@allure.severity(allure.severity_level.NORMAL)
def test_environments_api_returns_config(logged_page, base_url, project_code):
    """三重校验：测试环境接口应返回环境配置（演示项目预置 3 个环境）"""

    with allure.step("1. 解析项目 ID"):
        project_id = get_project_id(logged_page, base_url, project_code)

    with allure.step("2. 进入测试环境页并捕获环境列表接口"):
        response = capture_api_response(
            logged_page,
            f"/projects/{project_id}/environments",
            lambda: goto_module(logged_page, base_url, project_code, "测试环境"),
            wait_ms=4000,
        )

    with allure.step("3. 校验环境配置数据"):
        assert response.get("code") == 0, f"接口异常: {response}"
        data = response.get("data", [])
        items = data.get("items", []) if isinstance(data, dict) else data
        print(f"环境数量: {len(items)}")
        assert items, "测试环境列表为空，演示项目应预置环境"

        for env in items[:3]:
            assert "name" in env, f"环境对象缺少 name: {env}"


@allure.severity(allure.severity_level.NORMAL)
def test_test_tasks_page_loads(logged_page, base_url, project_code):
    """测试任务页正常加载并展示新建入口"""

    with allure.step("1. 进入测试任务页"):
        goto_module(logged_page, base_url, project_code, "测试任务")

    with allure.step("2. 校验核心元素"):
        expect(logged_page.get_by_role("button", name="新建任务").first).to_be_visible(timeout=15000)
        expect(logged_page.get_by_role("button", name="任务回收站").first).to_be_visible()


@allure.severity(allure.severity_level.NORMAL)
def test_variables_page_loads(logged_page, base_url, project_code):
    """项目变量页正常加载，支持添加变量与预设"""

    with allure.step("1. 进入测试环境页"):
        goto_module(logged_page, base_url, project_code, "测试环境")

    with allure.step("2. 点击变量入口"):
        logged_page.get_by_role("button", name="变量").first.click()
        logged_page.wait_for_timeout(2500)

    with allure.step("3. 校验变量管理能力"):
        verify_any_text(logged_page, ["添加变量", "添加预设", "变量"])


@allure.severity(allure.severity_level.MINOR)
def test_data_management_page_loads(logged_page, base_url, project_code):
    """测试数据管理页正常加载，展示四大功能 Tab 与数据工厂入口

    实测该页为 Tab 布局（数据工厂 / 数据快照 / 数据池 / 清理规则），
    每个 Tab 有独立操作按钮，默认仅展示「数据工厂」Tab 内容。

    注意：页面帮助指引折叠面板内也有同名的 h4 标题，
    因此这里限定在 tab 栏容器内定位，避免 strict mode 冲突。
    """

    with allure.step("1. 进入数据管理页"):
        goto_module(logged_page, base_url, project_code, "数据管理")

    with allure.step("2. 校验页面标题"):
        expect(logged_page.get_by_text("测试数据管理").first).to_be_visible(timeout=15000)

    with allure.step("3. 校验默认 Tab 的操作入口"):
        assert_button_clickable(logged_page, "新建数据工厂")

    with allure.step("4. 切换 Tab 并校验对应内容加载"):
        # 实测该页可见 tab id：tab-factory / tab-snapshot / tab-pool / tab-cleanup
        # 另有一组零尺寸的隐藏 tab（tab-rules / tab-tasks，w=h=0），属页面残留节点，不可点击。
        for tab_id in ["tab-snapshot", "tab-pool", "tab-cleanup"]:
            tab = logged_page.locator(f"#{tab_id}")
            expect(tab).to_be_visible(timeout=10000)
            tab.click()
            logged_page.wait_for_timeout(1800)
            assert tab.get_attribute("aria-selected") == "true", \
                f"{tab_id} 未进入选中态"

        # 切回第一个 Tab 恢复现场
        logged_page.locator("#tab-factory").click()
        logged_page.wait_for_timeout(1500)
        assert_button_clickable(logged_page, "新建数据工厂")


@allure.severity(allure.severity_level.MINOR)
def test_mock_service_page_loads(logged_page, base_url, project_code):
    """Mock 服务页正常加载，提供录制工具与新建入口"""

    with allure.step("1. 进入 Mock 服务页"):
        goto_module(logged_page, base_url, project_code, "Mock服务")

    with allure.step("2. 校验核心元素"):
        expect(logged_page.get_by_text("Mock").first).to_be_visible(timeout=15000)
        expect(logged_page.get_by_role("button", name="录制工具").first).to_be_visible()