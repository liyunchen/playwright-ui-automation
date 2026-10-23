"""项目管理模块 UI 自动化用例。

覆盖：项目列表加载、按名称/代码搜索、进入项目、项目内导航跳转、资产统计。
"""
import allure
import pytest
from playwright.sync_api import expect

from pages.project_page import (
    goto_projects,
    search_project,
    clear_project_search,
    assert_project_visible,
    assert_project_absent,
    open_project,
    goto_module,
    assert_in_project,
    get_project_stats,
    get_project_id,
)
from pages.assertion_helpers import (
    capture_api_response,
    assert_api_success,
    verify_texts,
    take_screenshot,
)

PROJECT_NAME = "QA自动化平台演示项目"


@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.smoke
def test_projects_list_loads_with_data(logged_page, base_url, project_code):
    """项目列表正常加载出项目数据与操作入口"""

    with allure.step("1. 打开项目列表页"):
        goto_projects(logged_page, base_url)

    with allure.step("2. 校验核心元素可见"):
        expect(logged_page.get_by_text("项目列表").first).to_be_visible(timeout=15000)
        verify_texts(logged_page, ["SQL执行器", "数据同步", "创建项目"])

    with allure.step("3. 校验演示项目在列表中"):
        assert_project_visible(logged_page, PROJECT_NAME)


@allure.severity(allure.severity_level.NORMAL)
def test_project_search_by_code(logged_page, base_url, project_code):
    """按项目代码搜索能命中目标项目"""

    with allure.step("1. 进入项目列表并按代码搜索"):
        goto_projects(logged_page, base_url)
        search_project(logged_page, project_code)

    with allure.step("2. 校验搜索命中"):
        assert_project_visible(logged_page, PROJECT_NAME)
        assert logged_page.get_by_text(project_code).first.is_visible()

    with allure.step("3. 清空搜索恢复列表"):
        clear_project_search(logged_page)
        expect(logged_page.get_by_text("项目列表").first).to_be_visible()


@allure.severity(allure.severity_level.NORMAL)
def test_project_search_no_match(logged_page, base_url):
    """搜索不存在的关键字返回空态提示"""

    with allure.step("1. 搜索不存在的项目名"):
        goto_projects(logged_page, base_url)
        search_project(logged_page, "不存在的项目_zzz_999")

    with allure.step("2. 校验空态提示"):
        assert_project_absent(logged_page, "不存在的项目_zzz_999")

    with allure.step("3. 恢复搜索"):
        clear_project_search(logged_page)


@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.smoke
def test_enter_project_and_load_dashboard(logged_page, base_url, project_code):
    """进入项目后工作台正常加载，展示资产统计与最近执行记录"""

    with allure.step("1. 进入项目工作台"):
        open_project(logged_page, base_url, project_code)

    with allure.step("2. 校验项目上下文与侧边栏"):
        assert_in_project(logged_page, project_code)
        verify_texts(logged_page, ["项目工作台", "手工用例", "代码用例", "自动化用例"])

    with allure.step("3. 校验资产统计模块可见"):
        expect(logged_page.get_by_text("项目资产").first).to_be_visible(timeout=15000)
        expect(logged_page.get_by_text("最近执行记录").first).to_be_visible()

    with allure.step("4. 留档演示截图"):
        take_screenshot(logged_page, "项目工作台")


@allure.severity(allure.severity_level.NORMAL)
def test_project_summary_api_returns_data(logged_page, base_url, project_code):
    """三重校验：UI 数据来源接口应返回当前项目统计（接口层校验）"""

    with allure.step("1. 解析项目数字 ID"):
        project_id = get_project_id(logged_page, base_url, project_code)
        print(f"项目 {project_code} 的数字 ID: {project_id}")

    with allure.step("2. 打开工作台并捕获 summary 接口"):
        response = capture_api_response(
            logged_page,
            f"/projects/{project_id}/summary",
            lambda: open_project(logged_page, base_url, project_code),
            wait_ms=4000,
        )

    with allure.step("3. 校验接口返回成功"):
        assert_api_success(response, "项目概览接口")

    with allure.step("4. 校验统计字段存在"):
        data = response.get("data", {})
        assert data, "summary 接口未返回统计数据"
        print(f"项目统计接口返回: {data}")


@allure.severity(allure.severity_level.NORMAL)
def test_navigate_between_modules(logged_page, base_url, project_code):
    """项目内各功能模块可正常跳转且路由正确"""

    modules = [
        ("手工用例", "手工用例"),
        ("代码用例", "代码用例"),
        ("自动化用例", "自动化用例"),
        ("测试环境", "测试环境"),
        ("测试报告", "测试报告"),
    ]

    for module_name, expected in modules:
        with allure.step(f"跳转并校验模块: {module_name}"):
            goto_module(logged_page, base_url, project_code, module_name)
            assert f"{project_code}" in logged_page.url, f"{module_name} 跳转后脱离项目上下文"
            expect(logged_page.get_by_text(expected).first).to_be_visible(timeout=15000)


@allure.severity(allure.severity_level.MINOR)
def test_project_dashboard_stats_render(logged_page, base_url, project_code):
    """工作台资产统计卡片能渲染出具体数值"""

    with allure.step("1. 进入工作台"):
        open_project(logged_page, base_url, project_code)

    with allure.step("2. 读取并校验统计卡片"):
        expect(logged_page.get_by_text("项目资产").first).to_be_visible(timeout=15000)
        stats = get_project_stats(logged_page)
        print(f"资产统计: {stats}")
        # 至少能读到一张统计卡片
        assert stats, "未读取到任何资产统计卡片"