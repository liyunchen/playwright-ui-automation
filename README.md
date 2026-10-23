# QA 自动化测试平台 · UI 自动化测试

> 基于 **Playwright + Pytest** 的 UI 自动化测试项目，验证 `qa-platform.example.com` 平台自身的
> 登录、项目管理、用例管理、接口管理、环境管理等模块的功能正确性与数据一致性。

[![用例](https://img.shields.io/badge/用例-29%20passed-22c55e)]() [![Python](https://img.shields.io/badge/Python-3.13-blue)]() [![Playwright](https://img.shields.io/badge/Playwright-1.64-2ead33)]()

---

## 演示素材

| 素材 | 说明 |
|------|------|
| `demo_assets/UI自动化演示精选.mp4` | 2 分 08 秒精选集，10 个章节带标题卡 |
| `demo_screenshots/01~10_*.png` | 2x 高清模块截图（1600×900） |
| `demo_videos/test_*.webm` | 29 条用例各自的独立录屏，文件名即用例名 |
| `demo_assets/项目介绍.md` | 简历要点 + 面试自述稿 + 追问准备 |

## 核心设计：UI + 接口 + 数据 三重校验

操作真实 UI 的同时通过 Playwright 网络监听捕获后端接口响应，再以接口真实数据做断言：

```python
project_id = get_project_id(page, base_url, project_code)
response = capture_api_response(
    page, f"/projects/{project_id}/summary",
    lambda: open_project(page, base_url, project_code),
    wait_ms=4000,
)
assert_api_success(response, "项目概览接口")
# 断言接口返回真实数据：22 手工用例 / 342 接口定义 / 7 自动化用例 / 63% 通过率
```

断言依据是接口数据而非页面文案，前端改版不会误判，也能校验页面未暴露的字段。

## 项目结构

```
├── code_testcases/            # 用例层（平台约定的代码用例扫描目录）
│   ├── 登录模块/              #   5 个用例：正确/错误密码、未授权重定向、飞书入口、演示环境提示
│   ├── 项目管理/              #   7 个用例：列表、搜索、工作台统计、多模块导航、概览接口断言
│   ├── 用例管理/              #   6 个用例：手工/代码/自动化用例、测试报告
│   ├── 接口管理/              #   6 个用例：目录树结构、资产统计、搜索过滤
│   └── 环境管理/              #   5 个用例：环境列表、配置接口、数据管理、变量、Mock
├── pages/                     # 页面层：Page Object 封装
│   ├── login_page.py
│   ├── project_page.py
│   └── assertion_helpers.py   #   通用断言 + 网络监听工具
├── common/                    # 公共层：API 客户端、断言模板、通配符递归匹配
├── config/env_config.yaml     # 多环境配置（qa / qa_staging）
├── scripts/                   # 演示素材制作脚本
├── conftest.py                # 全局 fixture（登录态复用、失败截图、录像）
├── Jenkinsfile                # Windows CI
├── zadig-test-script.sh       # Linux 容器 CI（含飞书通知）
└── pytest.ini
```

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env             # 填入 qa_password 等真实值
```

## 运行

```bash
pytest                              # 全部用例（默认 qa 环境）
pytest -m smoke                    # 冒烟
pytest code_testcases/登录模块       # 按模块
pytest --env=qa_staging            # 切换环境
allure serve reports/allure-results # 生成报告

VIDEO_DIR=demo_videos pytest        # 开启录像，产出每用例独立 webm
```

## 环境变量

| 变量 | 作用 |
|------|------|
| `qa_password` | 平台登录口令（被 `${VAR}` 引用） |
| `QA_URL` | 覆盖被测平台地址 |
| `QA_USERNAME` | 覆盖登录账号 |
| `QA_PROJECT_CODE` | 覆盖项目代码，默认 `qa_demo` |
| `VIDEO_DIR` | 设置后开启录像 |
| `HEADLESS` | 无头模式，默认 false |
| `KEEP_BROWSER` | 用例结束后保留浏览器 |

真实凭证仅存于 `.env`（已在 `.gitignore` 中）与 CI 凭证中心，仓库内无任何明文口令。

## 工程约定（踩坑记录）

1. **strict mode 冲突** — 登录页同时存在「登录」与「使用飞书登录」，需 `exact=True` 精确匹配。
2. **接口 URL 带时间戳** — 平台所有 GET 追加 `?_t=<ms>`，匹配路径前先剥掉查询串。
3. **统计接口用数字 ID** — 页面路由用项目 code，统计接口用数字 `project_id`，需先解析。
4. **禁止嵌套 `sync_playwright()`** — 与 session 级 browser fixture 冲突（`Sync API inside asyncio loop`）。
5. **错误提示是自动消失的 toast** — 断言登录失败应基于接口状态码而非页面文案。
6. **401 响应体不可读** — 失败响应触发跳转后无法读取 body，改用状态码断言。
7. **自研树组件** — 接口目录用 `.tree-item.tree-api`，非 Element Plus 的 `.el-tree-node__label`。
8. **零尺寸残留 Tab** — 数据管理页存在 `w=h=0` 的隐藏 tab 副本，需按 id 定位。
9. **录像重命名时机** — 必须在 `page.close()` 之前取 `page.video`，否则录像退化为随机文件名。
10. **平台扫描目录** — 平台从 `code_testcases` 扫描代码用例，用例必须置于该目录。

更完整说明见 [`项目指南.md`](项目指南.md)。

## CI

- **Jenkinsfile** — Windows 节点，参数化执行，按 marker 过滤，飞书通知
- **zadig-test-script.sh** — Linux 容器，报告上传对象存储后推送飞书卡片

所有 webhook、AK/SK、平台口令均从环境变量或 CI 凭证注入，脚本内无硬编码凭证。