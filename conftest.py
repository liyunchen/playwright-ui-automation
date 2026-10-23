# conftest.py — 兼容UI自动化和接口自动化
import pytest
from playwright.sync_api import sync_playwright
import os
import re
import time
import logging
import allure
import yaml
import pymysql

from common.api_client import ApiClient
from common.api_login import api_login

# ========== 日志配置 ==========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("qa_test")

# ========== 加载 .env（凭证明文不进仓库） ==========
def load_dotenv():
    """极简 .env 加载器：已存在的系统环境变量优先，不覆盖"""
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_file):
        return
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


load_dotenv()


# ========== ${VAR} 占位符解析 ==========
_PLACEHOLDER_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def resolve_placeholders(value, context=""):
    """递归解析配置中的 ${VAR} 占位符，取值来源优先级：系统环境变量 > .env

    未提供变量时保留占位符原样，由 db fixture / 登录逻辑决定跳过或报错，
    避免因缺凭证导致整个会话在import 阶段就崩掉。
    """
    if isinstance(value, str):
        def _replace(match):
            var_name = match.group(1)
            resolved = os.environ.get(var_name)
            if resolved is None:
                logger.warning(f"配置项 {context or 'root'} 引用的环境变量 {var_name} 未设置，将跳过依赖该凭证的测试")
                return match.group(0)
            return resolved
        return _PLACEHOLDER_PATTERN.sub(_replace, value)
    if isinstance(value, dict):
        return {k: resolve_placeholders(v, f"{context}.{k}" if context else k) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_placeholders(item, f"{context}[{i}]") for i, item in enumerate(value)]
    return value


# ========== 读取环境配置 ==========
def load_env_config(env_name):
    """根据环境名称加载对应配置

    优先级：系统环境变量 / .env 覆盖 > yaml 中的脱敏占位值。
    这样仓库可以安全提交脱敏配置，而实际运行环境（自建环境、
    本地调试）通过注入真实地址与账号即可覆盖，无需改代码。

    覆盖项：
      QA_URLQA_USERNAME / QA_PASSWORD   平台地址与账号，口令走 ${VAR}
    """
    config_path = os.path.join(os.path.dirname(__file__), "config", "env_config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        all_config = yaml.safe_load(f)
    if env_name not in all_config:
        raise ValueError(f"未知环境: {env_name}，可选: {list(all_config.keys())}")
    config = resolve_placeholders(all_config[env_name], env_name)

    # 支持用 QA_URL / QA_USERNAME 环境变量覆盖，便于多环境与多账号切换
    url_override = os.environ.get("QA_URL", "").strip()
    if url_override:
        config["url"] = url_override.rstrip("/")
        config["api_base_url"] = f"{config['url']}/api/v1"

    user_override = os.environ.get("QA_USERNAME", "").strip()
    if user_override:
        config["username"] = user_override

    project_override = os.environ.get("QA_PROJECT_CODE", "").strip()
    if project_override:
        config["project_code"] = project_override

    return config


def pytest_addoption(parser):
    """添加命令行参数"""
    parser.addoption("--env", action="store", default="qa", help="运行环境: qa/qa_staging")


@pytest.fixture(scope="session")
def env_config(request):
    """环境配置 fixture，返回当前环境的完整配置"""
    env_name = request.config.getoption("--env")
    return load_env_config(env_name)


# ========== 自动标记：根据目录自动添加 ui/api marker ==========
def pytest_collection_modifyitems(items):
    for item in items:
        test_path = str(item.fspath)
        if "/ui/" in test_path or "\\ui\\" in test_path:
            item.add_marker(pytest.mark.ui)
        elif "/api/" in test_path or "\\api\\" in test_path:
            item.add_marker(pytest.mark.api)


# ========== API 客户端夹具 ==========
@pytest.fixture(scope="session")
def api_client(env_config):
    """API 客户端 fixture，自动登录换取 token。"""
    base_url = env_config.get("api_base_url") or f"{env_config['url'].rstrip('/')}/api/v1"
    client = ApiClient(base_url)
    api_login(client, env_config["username"], env_config["password"])
    return client

# ========== 钩子函数：仅捕获 call 阶段（断言失败属于该阶段） ==========
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    # 仅为 call 阶段（用例执行阶段，断言失败属于此阶段）赋值
    if rep.when == "call":
        setattr(item, "rep_call", rep)

# ========== 视频录制（可选，用于演示与问题复现） ==========
def _new_context(browser, request, **kwargs):
    """统一的 context 创建入口，按需开启录像

    开启方式：运行前export VIDEO_DIR=demo_videos（默认关闭，不影响常规 CI）
    """
    video_dir = os.environ.get("VIDEO_DIR", "").strip()
    if not video_dir:
        return browser.new_context(**kwargs)

    os.makedirs(video_dir, exist_ok=True)
    context = browser.new_context(
        record_video_dir=video_dir,
        record_video_size=kwargs.pop("video_size", {"width": 1280, "height": 720}),
        **kwargs,
    )
    request.node._video_dir = video_dir
    return context


def _finalize_video(context, request, test_name, page=None):
    """关闭 context 会触发视频落盘，用例结束后把随机名改为用例名

    注意：必须在 page.close() 之前（或传入 page 引用）取 video，
    否则 context.pages 已被清空，取不到 video 对象会导致录像无法命名。
    """
    if not os.environ.get("VIDEO_DIR", "").strip():
        return
    try:
        if page is None:
            page = context.pages[0] if context.pages else None
        video = page.video if page and not page.is_closed() else None
        context.close()
        if video:
            video_path = video.path()
            video_dir = getattr(request.node, "_video_dir", "demo_videos")
            target = os.path.join(video_dir, f"{test_name}.webm")
            video.save_as(target)
            # save_as 后原始随机名文件仍会保留，删掉避免 demo_videos 里堆垃圾
            if os.path.exists(video_path) and os.path.abspath(video_path) != os.path.abspath(target):
                try:
                    os.remove(video_path)
                except OSError:
                    pass
            logger.info(f"用例录像已保存：{target}")
    except Exception as e:
        logger.error(f"视频保存失败：{type(e).__name__} - {e}")


# ========== 浏览器夹具（仅UI测试使用） ==========
@pytest.fixture(scope="session")
def browser(request):
    # 检查是否是API测试，如果是则跳过浏览器初始化
    if hasattr(request, 'node') and request.node.get_closest_marker('api'):
        pytest.skip("API测试不需要浏览器")

    with sync_playwright() as p:
        is_headless = os.environ.get("HEADLESS", "false").lower() == "true"
        browser_type = os.environ.get("BROWSER", "chromium").lower()
        launcher = getattr(p, browser_type, p.chromium)
        # 录像需要非无头模式才能看到真实操作过程
        if os.environ.get("VIDEO_DIR", "").strip():
            is_headless = False
        browser = launcher.launch(headless=is_headless, slow_mo=500)
        yield browser
        browser.close()

# ========== 移动端页面夹具 ==========
@pytest.fixture(scope="function")
def mobile_page(browser, request):
    """模拟 iPhone 14 的移动端页面"""
    context = _new_context(
        browser,
        request,
        viewport={"width": 390, "height": 844},
        device_scale_factor=3,
        is_mobile=True,
        has_touch=True,
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/16.0 Mobile/15E148 Safari/604.1"
        ),
    )
    page = context.new_page()
    yield page

    # 失败截图逻辑（复用 page fixture 的截图机制）
    item = request.node
    if hasattr(item, "rep_call") and item.rep_call.failed:
        screenshot_dir = "failed_screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)
        test_name = item.name
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        screenshot_path = os.path.abspath(f"{screenshot_dir}/{test_name}_{timestamp}.png")
        try:
            time.sleep(2)
            if not page.is_closed():
                page.screenshot(path=screenshot_path, full_page=True, timeout=10000)
                allure.attach.file(
                    source=screenshot_path,
                    name=f"断言失败截图_{test_name}",
                    attachment_type=allure.attachment_type.PNG,
                    extension="png",
                )
        except Exception as e:
            logger.error(f"移动端截图失败：{type(e).__name__} - {str(e)}")

    keep_open = os.environ.get("KEEP_BROWSER", "false").lower() == "true"
    if not keep_open:
        _finalize_video(context, request, request.node.name, page=page)

# ========== 页面夹具：确保断言失败触发截图+绑定 ==========
@pytest.fixture(scope="function")
def page(browser, request):
    context = _new_context(browser, request)
    page = context.new_page()
    yield page  # 执行用例（包含断言）

    # ========== 核心：仅判断 call 阶段失败（断言失败必触发） ==========
    item = request.node
    if hasattr(item, "rep_call") and item.rep_call.failed:
        # 1. 创建截图目录
        screenshot_dir = "failed_screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)  # 简化创建目录逻辑

        # 2. 生成唯一截图名（绝对路径）
        test_name = item.name
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        screenshot_path = os.path.abspath(f"{screenshot_dir}/{test_name}_{timestamp}.png")

        try:
            # 3. 强制截图（断言失败后页面可能未关闭，优先用page截图）
            # 增加超时+延迟，确保截图成功
            time.sleep(2)  # 延长延迟，避免页面瞬间关闭
            if not page.is_closed():
                page.screenshot(
                    path=screenshot_path,
                    full_page=True,
                    timeout=10000  # 超时10秒，避免截图卡死
                )
                logger.info(f"断言失败，截图已保存：{screenshot_path}")

                # 4. 绑定截图到 Allure（核心步骤，绝对路径+明确类型）
                allure.attach.file(
                    source=screenshot_path,
                    name=f"断言失败截图_{test_name}",
                    attachment_type=allure.attachment_type.PNG,
                    extension="png"
                )
                logger.info("截图已绑定到 Allure 报告")
            else:
                # 兜底：page已关闭，用context新建临时页面截图
                temp_page = context.new_page()
                temp_page.screenshot(path=screenshot_path, full_page=True)
                temp_page.close()
                logger.info(f"页面已关闭，通过新页面生成截图：{screenshot_path}")
                allure.attach.file(
                    source=screenshot_path,
                    name=f"断言失败截图_{test_name}",
                    attachment_type=allure.attachment_type.PNG
                )
        except Exception as e:
            # 打印详细错误，便于排查
            logger.error(f"截图/绑定失败：{type(e).__name__} - {str(e)}")
            # 兜底：手动添加错误日志到报告
            allure.attach(
                body=f"截图失败原因：{type(e).__name__} - {str(e)}",
                name="截图失败日志",
                attachment_type=allure.attachment_type.TEXT
            )

    # 最后关闭页面和上下文（截图完成后）
    keep_open = os.environ.get("KEEP_BROWSER", "false").lower() == "true"
    if not keep_open:
        # 录像重命名必须在 page.close() 之前取到 video，故先传 page 引用
        _finalize_video(context, request, request.node.name, page=page)



# ========== 平台访问参数夹具 ==========
@pytest.fixture(scope="session")
def base_url(env_config):
    """被测平台根地址，如 https://qa-platform.example.com"""
    return env_config["url"].rstrip("/")


@pytest.fixture(scope="session")
def project_code(env_config):
    """演示项目代码，平台路由形如 /{project_code}/{module}"""
    return env_config.get("project_code", "qa_demo")


@pytest.fixture(scope="session")
def platform_username(env_config):
    return env_config["username"]


@pytest.fixture(scope="session")
def platform_password(env_config):
    return env_config["password"]


# ========== 登录态复用夹具 ==========
@pytest.fixture(scope="session")
def auth_state(browser, base_url, platform_username, platform_password):
    """以一次真实登录换取 storage_state，供后续用例复用会话。

    不在 fixture 内嵌套 sync_playwright()——那会与 session 级 browser
    fixture 的事件循环冲突（Sync API inside asyncio loop）。
    这里直接复用 browser，另开一个 context 完成登录即可。

    好处：避免每个用例重复走登录流程，既提速也降低登录页变动带来的脆弱性。
    """
    import json
    from pathlib import Path

    from pages.login_page import platform_login

    state_file = Path("demo_screenshots") / "auth_state.json"
    if state_file.exists():
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            if data.get("base_url") == base_url and data.get("username") == platform_username:
                logger.info(f"复用已有登录态: {state_file}")
                return data
        except Exception as e:
            logger.warning(f"登录态文件损坏，将重新登录: {e}")

    context = browser.new_context()
    page = context.new_page()
    try:
        platform_login(page, base_url, platform_username, platform_password)
        state = context.storage_state()
    finally:
        context.close()

    state_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "base_url": base_url,
        "username": platform_username,
        "storage_state": state,
    }
    state_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"登录态已保存: {state_file}")
    return payload


# ========== 已登录页面夹具 ==========
@pytest.fixture(scope="function")
def logged_page(browser, request, auth_state):
    """已登录态的页面，用于跳过登录环节的用例。"""
    context = _new_context(
        browser,
        request,
        storage_state=auth_state["storage_state"],
        viewport={"width": 1600, "height": 1000},
    )
    page = context.new_page()
    yield page
    _finalize_video(context, request, request.node.name, page=page)
