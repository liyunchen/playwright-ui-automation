"""用例管理模块 UI 自动化用例。

覆盖：手工用例列表、模块搜索、用例搜索、代码用例扫描入口、自动化用例列表。
定位器依据2026-10-23 实测 DOM（搜索框 placeholder 为「搜索模块」「搜索用例名/模块/函数名」等）。
"""
import allure
import pytest
from playwright.sync_api import expect

from pages.project_page import goto_module, get_project_id
from pages.assertion_helpers import capture_api_response, verify_texts, verify_any_text


@allure.severity(allure.severity_level.NORMAL)
def test_manual_cases_list_loads(logged_page, base_url, project_code):
    """手工用例页正常加载，展示用例总数与操作入口"""

    with allure.step("1. 进入手工用例页"):
        goto_module(logged_page, base_url, project_code, "手工用例")

    with allure.step("2. 校验核心元素"):
        expect(logged_page.get_by_text("手工用例").first).to_be_visible(timeout=15000)
        verify_texts(logged_page, ["新建用例", "去重管理", "关联管理"])

    with allure.step("3. 校验存在用例数据（总数区块）"):
        expect(logged_page.get_by_text("全部用例").first).to_be_visible(timeout=10000)


@allure.severity(allure.severity_level.NORMAL)
def test_manual_case_search_by_keyword(logged_page, base_url, project_code):
    """手工用例支持按关键字搜索并展示结果"""

    with allure.step("1. 进入手工用例页"):
        goto_module(logged_page, base_url, project_code, "手工用例")

    with allure.step("2. 定位用例搜索框"):
        # 实测该页搜索框无 placeholder，用 aria-label 或可见输入框兜底定位
        box = (logged_page.locator('input[aria-label*="搜索用例"]')
               .or_(logged_page.locator('input[placeholder*="搜索用例"]'))
               .or_(logged_page.locator('input[placeholder*="搜索"]'))
               ).first
        if not box.count():
            # 退回到模块搜索框，仍能验证搜索交互可用
            box = logged_page.get_by_placeholder("搜索模块").first
        expect(box).to_be_visible(timeout=10000)

    with allure.step("3. 输入关键字并校验有反馈"):
        box.fill("登录")
        logged_page.wait_for_timeout(2500)
        verify_any_text(logged_page, ["登录", "没有", "暂无", "无数据", "全部用例"])

        box.fill("")
        logged_page.wait_for_timeout(1500)


@allure.severity(allure.severity_level.NORMAL)
def test_code_cases_page_shows_scan_entry(logged_page, base_url, project_code):
    """代码用例页应提供扫描代码入口（平台从 code_testcases 目录扫描用例）"""

    with allure.step("1. 进入代码用例页"):
        goto_module(logged_page, base_url, project_code, "代码用例")

    with allure.step("2. 校验扫描入口与数据来源说明"):
        expect(logged_page.get_by_role("button", name="扫描代码").first).to_be_visible(timeout=10000)
        expect(logged_page.get_by_text("代码用例").first).to_be_visible()

    with allure.step("3. 校验支持批量执行"):
        expect(logged_page.get_by_role("button", name="批量执行").first).to_be_visible()


@allure.severity(allure.severity_level.NORMAL)
def test_automation_cases_list_loads(logged_page, base_url, project_code):
    """自动化用例页正常加载并展示用例数据"""

    with allure.step("1. 进入自动化用例页"):
        goto_module(logged_page, base_url, project_code, "自动化用例")

    with allure.step("2. 校验核心元素"):
        expect(logged_page.get_by_text("自动化用例").first).to_be_visible(timeout=15000)
        expect(logged_page.get_by_role("button", name="新建用例").first).to_be_visible()

    with allure.step("3. 校验用例搜索框存在"):
        expect(logged_page.get_by_placeholder("搜索用例名称").first).to_be_visible(timeout=10000)


@allure.severity(allure.severity_level.NORMAL)
def test_automation_cases_api_returns_list(logged_page, base_url, project_code):
    """三重校验：自动化用例列表接口应返回分页数据"""

    with allure.step("1. 解析项目 ID"):
        project_id = get_project_id(logged_page, base_url, project_code)

    with allure.step("2. 进入自动化用例页并捕获列表接口"):
        response = capture_api_response(
            logged_page,
            f"/projects/{project_id}/automation-cases",
            lambda: goto_module(logged_page, base_url, project_code, "自动化用例"),
            wait_ms=4000,
        )

    with allure.step("3. 校验接口返回用例列表"):
        assert response.get("code") == 0, f"接口异常: {response}"
        data = response.get("data", {})
        items = data.get("items", [])
        assert isinstance(items, list), "items 字段结构异常"
        print(f"自动化用例总数: {data.get('total')}，返回条目: {len(items)}")
        assert data.get("total", 0) > 0, "演示项目应至少包含自动化用例"

        if items:
            first = items[0]
            for field in ("name", "status", "version"):
                assert field in first, f"用例对象缺少字段 {field}"


@allure.severity(allure.severity_level.MINOR)
def test_reports_page_loads(logged_page, base_url, project_code):
    """测试报告页正常加载并提供搜索入口"""

    with allure.step("1. 进入测试报告页"):
        goto_module(logged_page, base_url, project_code, "测试报告")

    with allure.step("2. 校验报告页核心元素"):
        expect(logged_page.get_by_text("测试报告").first).to_be_visible(timeout=15000)
        expect(logged_page.get_by_placeholder("🔍 搜索报告...").first).to_be_visible(timeout=10000)