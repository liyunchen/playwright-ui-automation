"""项目列表与项目工作台操作封装。

定位器依据：2026-10-23 实测 DOM
- 项目列表页 /projects：按钮「SQL执行器」「数据同步」「创建项目」「进入」，搜索框 placeholder「搜索项目名称或代码」
- 项目内路由形如 /qa_demo/manual-cases，侧边栏含「项目工作台」「手工用例」等
"""
from playwright.sync_api import Page, expect

# 项目内各功能模块的路由（实测有效）
PROJECT_ROUTES = {
    "项目工作台": "/dashboard",
    "手工用例": "/manual-cases",
    "代码用例": "/code-cases",
    "接口管理": "/api-catalog",
    "自动化用例": "/automation-cases",
    "测试任务": "/test-tasks",
    "测试计划": "/test-plans",
    "测试环境": "/environment",
    "数据管理": "/data-management",
    "测试报告": "/reports",
    "性能测试": "/performance",
    "Mock服务": "/mock",
}


def goto_projects(page: Page, base_url: str):
    """进入项目列表页。"""
    page.goto(f"{base_url}/projects", wait_until="domcontentloaded")
    page.wait_for_timeout(2000)


def search_project(page: Page, keyword: str):
    """在项目列表页按名称或代码搜索。"""
    page.get_by_placeholder("搜索项目名称或代码").fill(keyword)
    page.wait_for_timeout(1500)


def clear_project_search(page: Page):
    """清空项目搜索条件。"""
    box = page.get_by_placeholder("搜索项目名称或代码")
    box.fill("")
    page.wait_for_timeout(1500)


def assert_project_visible(page: Page, project_name: str):
    """断言指定项目出现在列表中。"""
    expect(page.get_by_text(project_name).first).to_be_visible(timeout=10000)


def assert_project_absent(page: Page, keyword: str):
    """断言搜索结果为空（实测平台空态文案为「没有匹配的项目」）。"""
    expect(page.get_by_text("没有匹配的项目").first).to_be_visible(timeout=10000)


def get_project_id(page: Page, base_url: str, project_code: str) -> str:
    """解析项目数字 ID。

    平台的统计类接口用数字 project_id 而非 code，
    这里通过列表接口响应或页面链接提取，保证接口断言能定位到正确项目。
    """
    import re
    # 优先从当前 URL 里已带的项目上下文推断
    page.goto(f"{base_url}/projects", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)

    captured = {}

    def handle(response):
        # 平台所有 GET 请求都带 _t= 时间戳，需先剥掉查询串再判断
        path = response.url.split("/api/v1")[-1].split("?")[0]
        if path == "/projects":
            try:
                data = response.json()
                payload = data.get("data", {})
                items = payload.get("items", payload if isinstance(payload, list) else [])
                for it in items:
                    if it.get("code") == project_code:
                        captured["id"] = str(it.get("id"))
            except Exception:
                pass

    page.on("response", handle)
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    page.remove_listener("response", handle)

    assert captured.get("id"), f"未能解析项目 {project_code} 的数字 ID"
    return captured["id"]


def open_project(page: Page, base_url: str, project_code: str):
    """通过项目代码直接进入项目工作台。

    平台路由规则为 /{project_code}/{module}，直接拼路由比点击更快也更稳定。
    """
    page.goto(f"{base_url}/{project_code}/dashboard", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)


def goto_module(page: Page, base_url: str, project_code: str, module: str):
    """在项目内跳转到指定功能模块。"""
    if module not in PROJECT_ROUTES:
        raise ValueError(f"未知模块: {module}，可选: {list(PROJECT_ROUTES.keys())}")
    page.goto(f"{base_url}/{project_code}{PROJECT_ROUTES[module]}",
              wait_until="domcontentloaded")
    page.wait_for_timeout(2500)


def assert_module_loaded(page: Page, expected_text: str):
    """断言模块页面加载完成（校验标题类关键文本）。"""
    expect(page.get_by_text(expected_text).first).to_be_visible(timeout=15000)


def assert_in_project(page: Page, project_code: str):
    """断言当前处于指定项目上下文。"""
    expect(page.get_by_text(project_code).first).to_be_visible(timeout=10000)


def get_project_stats(page: Page):
    """读取项目工作台的资产统计（用例数、接口数、自动化用例数等）。

    返回 dict，键为统计项名称，值为页面上的数字文本。
    """
    cards = page.locator(".stat-card, .el-card, [class*='stat']")
    stats = {}
    for i in range(min(cards.count(), 12)):
        try:
            text = cards.nth(i).inner_text().strip()
            if text:
                stats[f"card_{i}"] = " | ".join(text.split("\n")[:3])
        except Exception:
            continue
    return stats