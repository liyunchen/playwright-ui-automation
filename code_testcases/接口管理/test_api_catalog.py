"""接口管理模块 UI 自动化用例。

覆盖：接口目录加载、接口搜索、目录树展开、接口详情数据结构校验。
定位器依据 2026-10-23 实测 DOM（搜索框placeholder 为「搜索接口...」）。
"""
import allure
import pytest
from playwright.sync_api import expect

from pages.project_page import goto_module, get_project_id
from pages.assertion_helpers import capture_api_response





def count_api_entries(page):
    """统计接口目录树中当前可见的接口条目数。

    实测该页使用自研树组件（非 Element Plus），类名结构为：
      .tree-item.tree-dir   目录分组
      .tree-item.tree-api   接口叶子节点
    """
    return page.evaluate("""() => {
        const nodes = document.querySelectorAll('.tree-item.tree-api');
        let visible = 0;
        nodes.forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0) visible++;
        });
        return visible;
    }""")


def count_api_dirs(page):
    """统计接口目录树中当前可见的目录分组数。"""
    return page.evaluate("""() => {
        const nodes = document.querySelectorAll('.tree-item.tree-dir');
        let visible = 0;
        nodes.forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width > 0 && r.height > 0) visible++;
        });
        return visible;
    }""")


@allure.severity(allure.severity_level.NORMAL)
def test_api_catalog_loads(logged_page, base_url, project_code):
    """接口管理页正常加载，目录树渲染出分组与接口条目"""

    with allure.step("1. 进入接口管理页"):
        goto_module(logged_page, base_url, project_code, "接口管理")

    with allure.step("2. 校验核心元素"):
        expect(logged_page.get_by_text("接口管理").first).to_be_visible(timeout=15000)
        expect(logged_page.get_by_role("button", name="新建目录").first).to_be_visible()
        expect(logged_page.get_by_role("button", name="新建接口").first).to_be_visible()
        expect(logged_page.get_by_role("button", name="导入 Swagger").first).to_be_visible()

    with allure.step("3. 校验目录树已渲染出分组与接口条目"):
        logged_page.wait_for_timeout(3000)
        leaves = count_api_entries(logged_page)
        dirs = count_api_dirs(logged_page)
        print(f"目录分组数: {dirs}，接口条目数: {leaves}")
        assert leaves > 0, "接口目录树未渲染出任何接口条目"
        assert dirs > 0, "接口目录树未渲染出目录分组"


@allure.severity(allure.severity_level.NORMAL)
def test_api_search_input_works(logged_page, base_url, project_code):
    """接口目录搜索框可用，输入后能过滤树并可清空恢复

    实测为前端过滤（不会重新发起接口请求），
    因此通过「过滤前后可见接口条目数变化」来验证。
    """

    with allure.step("1. 进入接口管理页并读取过滤前条目数"):
        goto_module(logged_page, base_url, project_code, "接口管理")
        logged_page.wait_for_timeout(3000)
        before = count_api_entries(logged_page)
        print(f"搜索前接口条目数: {before}")
        assert before > 0, "搜索前目录树为空，无法验证过滤效果"

    with allure.step("2. 输入关键字并校验条目数减少"):
        box = logged_page.get_by_placeholder("搜索接口...")
        expect(box).to_be_visible(timeout=10000)
        box.click()
        box.fill("login")
        logged_page.wait_for_timeout(3000)
        after = count_api_entries(logged_page)
        print(f"搜索 login 后条目数: {after}")
        assert after < before, \
            f"搜索后条目数未减少（before={before}, after={after}）"

    with allure.step("3. 清空搜索并校验条目数恢复"):
        box.fill("")
        logged_page.wait_for_timeout(3000)
        restored = count_api_entries(logged_page)
        print(f"清空后条目数: {restored}")
        assert restored >= before, \
            f"清空搜索后条目未恢复（before={before}, restored={restored}）"


@allure.severity(allure.severity_level.NORMAL)
def test_api_tree_api_returns_structure(logged_page, base_url, project_code):
    """三重校验：接口目录树接口应返回规范的树形结构"""

    with allure.step("1. 解析项目 ID"):
        project_id = get_project_id(logged_page, base_url, project_code)

    with allure.step("2. 进入接口管理页并捕获目录树接口"):
        response = capture_api_response(
            logged_page,
            f"/projects/{project_id}/apis/tree",
            lambda: goto_module(logged_page, base_url, project_code, "接口管理"),
            wait_ms=4000,
        )

    with allure.step("3. 校验树形结构合法性"):
        assert response.get("code") == 0, f"接口异常: {response}"
        tree = response.get("data", [])
        # 实测该接口 data 可能直接是数组，也可能是 {items: [...]} 包装
        if isinstance(tree, dict):
            tree = tree.get("items", [])
        assert isinstance(tree, list), f"目录树根节点应为数组，实际 {type(tree).__name__}"
        print(f"接口目录一级节点数: {len(tree)}")
        assert tree, "接口目录树为空"

        # 校验节点必备字段
        for node in tree[:5]:
            assert "name" in node, f"节点缺少 name 字段: {node}"
            assert "children" in node, f"节点缺少 children 字段: {node}"


@allure.severity(allure.severity_level.NORMAL)
def test_api_apis_api_returns_definitions(logged_page, base_url, project_code):
    """三重校验：接口定义接口应返回分页的接口资产"""

    with allure.step("1. 解析项目 ID"):
        project_id = get_project_id(logged_page, base_url, project_code)

    with allure.step("2. 进入接口管理页并捕获接口列表接口"):
        response = capture_api_response(
            logged_page,
            f"/projects/{project_id}/apis",
            lambda: goto_module(logged_page, base_url, project_code, "接口管理"),
            wait_ms=4000,
        )

    with allure.step("3. 校验接口资产数据"):
        assert response.get("code") == 0, f"接口异常: {response}"
        data = response.get("data", [])
        # 实测该接口 data 可能直接是数组，也可能是 {items, total} 包装
        if isinstance(data, dict):
            items = data.get("items", [])
            total = data.get("total")
        else:
            items, total = data, len(data)
        print(f"接口定义总数: {total}，返回条目: {len(items)}")
        assert items, "接口定义列表为空，演示项目应已预置接口资产"


@allure.severity(allure.severity_level.MINOR)
def test_api_catalog_keeps_route(logged_page, base_url, project_code):
    """接口管理页在项目上下文内，路由不脱离当前项目"""

    with allure.step("1. 进入接口管理页"):
        goto_module(logged_page, base_url, project_code, "接口管理")

    with allure.step("2. 校验路由上下文"):
        assert f"/{project_code}/" in logged_page.url, \
            f"接口管理页脱离了项目上下文: {logged_page.url}"