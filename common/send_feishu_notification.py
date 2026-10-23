#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
发送飞书通知，按目录结构展示测试结果
"""
import requests
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

api_total = os.environ.get('API_TOTAL', '0')
api_passed = os.environ.get('API_PASSED', '0')
api_failed = os.environ.get('API_FAILED', '0')
api_pass_rate = os.environ.get('API_PASS_RATE', '0%')

# 读取格式化后的用例文本
try:
    with open('/tmp/ui_cases.txt', 'r', encoding='utf-8') as f:
        ui_cases_text = f.read()
except:
    ui_cases_text = '无'

try:
    with open('/tmp/api_cases.txt', 'r', encoding='utf-8') as f:
        api_cases_text = f.read()
except:
    api_cases_text = '无'

# 构建通知内容
status = "✅ 成功" if failed == '0' else "❌ 失败"
status_color = "green" if failed == '0' else "red"

# 构建详情文本
details = f"**整体通过率:** {pass_rate} ({passed}/{total})"

if int(ui_total) > 0:
    details += f"\n\n**UI自动化** (通过率: {ui_pass_rate})\n{ui_cases_text}"

if int(api_total) > 0:
    details += f"\n\n**接口自动化** (通过率: {api_pass_rate})\n{api_cases_text}"

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
        print(f"❌ 通知发送异常: {url[:40]}..., 错误: {str(e)}")

print("飞书通知发送完成")
