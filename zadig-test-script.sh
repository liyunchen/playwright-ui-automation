#!/bin/bash
set -e
TIME=$(date '+%Y-%m-%d-%H%M%S')
# 根据测试类型决定是否安装浏览器
if [ "$TEST_TYPE" != "api" ]; then
    # 检查浏览器是否已缓存，避免重复安装
    BROWSER_CACHE="/root/.cache/ms-playwright"
    if [ -d "$BROWSER_CACHE" ] && [ "$(ls -A $BROWSER_CACHE 2>/dev/null)" ]; then
        echo "========== 浏览器已缓存，跳过安装 =========="
    else
        echo "========== 安装 Playwright 浏览器 =========="
        playwright install $BROWSER
        cat >/tmp/bullseye-hwcloud.list <<'EOF'
deb https://mirrors.huaweicloud.com/debian bullseye main contrib non-free
deb https://mirrors.huaweicloud.com/debian bullseye-updates main contrib non-free
deb https://mirrors.huaweicloud.com/debian-security bullseye-security main contrib non-free
EOF
        mkdir -p /tmp/apt-empty /tmp/fakebin
        cat >/tmp/fakebin/apt-get <<'EOF'
#!/bin/sh
exec /usr/bin/apt-get \
  -o Dir::Etc::sourcelist=/tmp/bullseye-hwcloud.list \
  -o Dir::Etc::sourceparts=/tmp/apt-empty \
  "$@"
EOF
        chmod +x /tmp/fakebin/apt-get
        PATH="/tmp/fakebin:$PATH" playwright install-deps
    fi
fi

echo "依赖安装完成"

################################################################执行测试阶段###############################################################################
echo "========== 清理旧报告 =========="
rm -rf /workspace/reports/allure-results
rm -rf /workspace/allure-results
mkdir -p /workspace/reports/allure-results

echo "========== 执行测试 =========="
export BROWSER=$BROWSER
export HEADLESS=$HEADLESS

# 构建 pytest 命令 - 同时生成 Allure 结果和 JUnit XML
PYTEST_CMD="pytest --env=$ENV --alluredir=/workspace/reports/allure-results --clean-alluredir --junitxml=/workspace/reports/junit-report.xml"

# 检查 pytest-xdist 是否安装
if pip show pytest-xdist > /dev/null 2>&1; then
    echo "pytest-xdist 已安装，启用并发执行"
    # 添加并发执行（根据测试类型调整并发数）
    if [ "$TEST_TYPE" = "api" ]; then
        # API测试可以高并发
        PYTEST_CMD="$PYTEST_CMD -n 8"
    else
        # UI测试并发数不宜过高，避免资源竞争
        PYTEST_CMD="$PYTEST_CMD -n 4"
    fi
else
    echo "pytest-xdist 未安装，跳过并发执行"
fi

# 添加测试类型过滤
if [ "$TEST_TYPE" != "all" ]; then
    PYTEST_CMD="$PYTEST_CMD -m $TEST_TYPE"
fi

# 添加自定义 marker 过滤
if [ -n "$TEST_MARKER" ]; then
    PYTEST_CMD="$PYTEST_CMD -m $TEST_MARKER"
fi

echo "执行命令: $PYTEST_CMD"
# 用例目录为 code_testcases（平台约定的代码用例扫描目录）
cd /workspace/autotest/code_testcases && $PYTEST_CMD || true  # 允许测试失败，继续生成报告
cd /workspace
echo "测试执行完成"

################################################################生产报告阶段###############################################################################
echo "========== 生成 Allure 报告 =========="
allure generate /workspace/reports/allure-results -o /workspace/reports/allure-report --clean

echo "========== 解析测试结果 =========="
python3 << 'EOF'
import json
from pathlib import Path
from collections import defaultdict

results_dir = Path("/workspace/reports/allure-results")

# 按 fullName 分组，去重（重试的用例会有多个结果文件）
test_results = defaultdict(list)

for file in results_dir.glob("*-result.json"):
    with open(file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        full_name = data.get('fullName', '')
        status = data.get('status', 'unknown')

        # 从 labels 中提取 suite 名称（文件名）
        suite_name = ''
        labels = data.get('labels', [])
        for label in labels:
            if label.get('name') == 'suite':
                suite_name = label.get('value', '')
                break

        test_results[full_name].append({'suite': suite_name, 'status': status})

# 分类统计：UI 自动化（模块目录：登录模块/项目管理/用例管理/接口管理/环境管理）
#            接口自动化（文件名以 test_api 开头）
ui_passed = []
ui_failed = []
api_passed = []
api_failed = []

for full_name, results in test_results.items():
    # 取最终状态：如果有任何一次通过，算通过
    final_status = 'passed' if any(r['status'] == 'passed' for r in results) else 'failed'

    # 从 suite 名称提取中文用例名
    suite_name = results[0]['suite']
    test_name = suite_name

    # 去掉 test_ 前缀，保留可读的用例名
    if suite_name.startswith('test_'):
        test_name = suite_name.replace('test_', '', 1)

    # 接口自动化用例以 test_api 开头，其余归入 UI 自动化
    if '/test_api' in full_name or suite_name.startswith('test_api'):
        if final_status == 'passed':
            api_passed.append(test_name)
        else:
            api_failed.append(test_name)
    else:
        if final_status == 'passed':
            ui_passed.append(test_name)
        else:
            ui_failed.append(test_name)

# 计算统计数据
ui_total = len(ui_passed) + len(ui_failed)
ui_pass_rate = f"{(len(ui_passed)/ui_total*100):.1f}%" if ui_total > 0 else "0%"

api_total = len(api_passed) + len(api_failed)
api_pass_rate = f"{(len(api_passed)/api_total*100):.1f}%" if api_total > 0 else "0%"

total = ui_total + api_total
passed = len(ui_passed) + len(api_passed)
failed = len(ui_failed) + len(api_failed)
pass_rate = f"{(passed/total*100):.1f}%" if total > 0 else "0%"

# 写成 shell 可 source 的格式
with open('/tmp/test_env.sh', 'w') as f:
    f.write(f"export TEST_TOTAL={total}\n")
    f.write(f"export TEST_PASSED={passed}\n")
    f.write(f"export TEST_FAILED={failed}\n")
    f.write(f'export TEST_PASS_RATE="{pass_rate}"\n')
    f.write(f"export UI_TOTAL={ui_total}\n")
    f.write(f"export UI_PASSED={len(ui_passed)}\n")
    f.write(f"export UI_FAILED={len(ui_failed)}\n")
    f.write(f'export UI_PASS_RATE="{ui_pass_rate}"\n')
    f.write(f'export UI_PASSED_NAMES="{",".join(ui_passed)}"\n')
    f.write(f'export UI_FAILED_NAMES="{",".join(ui_failed)}"\n')
    f.write(f"export API_TOTAL={api_total}\n")
    f.write(f"export API_PASSED={len(api_passed)}\n")
    f.write(f"export API_FAILED={len(api_failed)}\n")
    f.write(f'export API_PASS_RATE="{api_pass_rate}"\n')
    f.write(f'export API_PASSED_NAMES="{",".join(api_passed)}"\n')
    f.write(f'export API_FAILED_NAMES="{",".join(api_failed)}"\n')

print(f"总用例: {total}, 通过: {passed}, 失败: {failed}, 通过率: {pass_rate}")
print(f"UI自动化: {ui_total}, 通过: {len(ui_passed)}, 失败: {len(ui_failed)}, 通过率: {ui_pass_rate}")
print(f"接口自动化: {api_total}, 通过: {len(api_passed)}, 失败: {len(api_failed)}, 通过率: {api_pass_rate}")
EOF

# 加载环境变量
source /tmp/test_env.sh

################################################################上传报告到对象存储###############################################################################
# 安全要求：AK/SK 只能来自环境变量，绝不写入仓库；
# 桶策略建议设为私有（去掉 -acl=public-read），报告通过内网或鉴权链接访问。
echo "========== 上传 Allure 报告 =========="
ls -la /workspace/reports/allure-report/

if [ -z "${OBS_AK}" ] || [ -z "${OBS_SK}" ]; then
    echo "未配置 OBS_AK / OBS_SK，跳过报告上传"
    REPORT_UPLOADED=false
else
    obsutil config -i "${OBS_AK}" -k "${OBS_SK}" -e "${OBS_ENDPOINT:-obs.cn-south-1.myhuaweicloud.com}"
    # 注意：不加 -acl=public-read，避免测试报告公开可访问
    obsutil cp -r -f /workspace/reports/allure-report/ "obs://${OBS_BUCKET}/${ENV}/${TIME}/"
    REPORT_UPLOADED=true
fi

# 报告访问地址：由环境变量注入，不在脚本内写死内网域名
export ALLURE_REPORT_URL="${ALLURE_BASE_URL:-请配置 ALLURE_BASE_URL}/${ENV}/${TIME}/allure-report/"
echo "报告地址: $ALLURE_REPORT_URL"

# 被测平台地址：本项目测试 qa-platform.example.com 平台自身，多环境由 QA_URL 注入
export ENV_URL="${QA_URL:-https://qa-platform.example.com}"
echo "环境地址: $ENV_URL"

################################################################发送通知阶段###############################################################################
echo "========== 发送飞书通知 =========="
python3 << 'EOF'
import requests
import json
import os
from datetime import datetime

# 读取测试结果
total = os.environ.get('TEST_TOTAL', '0')
passed = os.environ.get('TEST_PASSED', '0')
failed = os.environ.get('TEST_FAILED', '0')
pass_rate = os.environ.get('TEST_PASS_RATE', '0%')

ui_total = os.environ.get('UI_TOTAL', '0')
ui_passed = os.environ.get('UI_PASSED', '0')
ui_failed = os.environ.get('UI_FAILED', '0')
ui_pass_rate = os.environ.get('UI_PASS_RATE', '0%')
ui_passed_names = os.environ.get('UI_PASSED_NAMES', '')
ui_failed_names = os.environ.get('UI_FAILED_NAMES', '')

api_total = os.environ.get('API_TOTAL', '0')
api_passed = os.environ.get('API_PASSED', '0')
api_failed = os.environ.get('API_FAILED', '0')
api_pass_rate = os.environ.get('API_PASS_RATE', '0%')
api_passed_names = os.environ.get('API_PASSED_NAMES', '')
api_failed_names = os.environ.get('API_FAILED_NAMES', '')

# 构建通知内容
status = "✅ 成功" if failed == '0' else "❌ 失败"
status_color = "green" if failed == '0' else "red"

def format_case_lines(names, icon):
    case_list = [name.strip() for name in names.split(',') if name.strip()]
    if not case_list:
        return "- 无"
    return "\n".join(f"{icon} {index}. {name}" for index, name in enumerate(case_list, 1))


def build_case_section(title, pass_rate_value, passed_names, failed_names):
    return (
        f"\n\n**{title}** (通过率: {pass_rate_value})\n"
        f"**✅ 通过用例**\n{format_case_lines(passed_names, '-')}\n\n"
        f"**❌ 失败用例**\n{format_case_lines(failed_names, '-')}"
    )


# 构建 UI/API 详情文本
details = f"**整体通过率:** {pass_rate} ({passed}/{total})"

if int(ui_total) > 0:
    details += build_case_section("UI自动化", ui_pass_rate, ui_passed_names, ui_failed_names)

if int(api_total) > 0:
    details += build_case_section("接口自动化", api_pass_rate, api_passed_names, api_failed_names)

payload = {
    "msg_type": "interactive",
    "card": {
        "header": {
            "title": {
                "content": f"🤖 UI 自动化测试报告 {status}",
                "tag": "plain_text"
            },
            "template": status_color
        },
        "elements": [
            {
                "tag": "div",
                "fields": [
                    {"is_short": True, "text": {"tag": "lark_md", "content": "**项目名称**\nQA 自动化测试平台"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**构建编号**\n{os.environ.get('BUILD_NUMBER', 'N/A')}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**测试环境**\n{os.environ.get('ENV', 'N/A')}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**测试类型**\n{os.environ.get('TEST_TYPE', 'all')}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**浏览器**\n{os.environ.get('BROWSER', 'chromium')}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**执行时间**\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}}
                ]
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": details
                }
            },
            {"tag": "hr"},
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "查看测试报告"},
                        "type": "primary",
                        "url": os.environ.get('ALLURE_REPORT_URL', '#')
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "访问测试环境"},
                        "type": "default",
                        "url": os.environ.get('ENV_URL', '#')
                    }
                ]
            }
        ]
    }
}

# 飞书 Webhook 地址列表（从环境变量读取，多个用英文逗号分隔）
raw_webhooks = os.environ.get('FEISHU_WEBHOOK_URLS', '')
webhook_urls = [u.strip() for u in raw_webhooks.split(',') if u.strip()]

if not webhook_urls:
    print("⚠️ 未配置 FEISHU_WEBHOOK_URLS，跳过飞书通知")
    raise SystemExit(0)

# 发送通知
for url in webhook_urls:
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"✅ 通知发送成功: {url[:40]}...")
        else:
            print(f"❌ 通知发送失败: {url[:40]}..., 状态码: {response.status_code}")
    except Exception as e:
        print(f"❌ 通知发送异常: {url}, 错误: {str(e)}")

print("飞书通知发送完成")
EOF

echo "========== 测试流程全部完成 =========="
