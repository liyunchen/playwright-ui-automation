#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解析 Allure 测试结果，按目录结构分组通过和失败的用例
用于替换 zadig-test-script.sh 中的 Python 脚本部分
"""
import json
import os
from pathlib import Path
from collections import defaultdict

DEBUG = os.environ.get('DEBUG_PARSE', '0') == '1'

results_dir = Path("/workspace/reports/allure-results")

# 按 fullName 分组，去重（重试的用例会有多个结果文件）
test_results = defaultdict(list)

for file in results_dir.glob("*-result.json"):
    with open(file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        full_name = data.get('fullName', '')
        status = data.get('status', 'unknown')

        # 从 labels 中提取 suite（文件名）和 package（模块路径）
        suite_name = ''
        package = ''
        labels = data.get('labels', [])
        for label in labels:
            if label.get('name') == 'suite':
                suite_name = label.get('value', '')
            elif label.get('name') == 'package':
                package = label.get('value', '')

        test_results[full_name].append({
            'suite': suite_name,
            'package': package,
            'status': status,
        })


def extract_module_and_name(full_name, package, suite_name):
    """
    从 package 或 fullName 提取模块名，从 suite_name 提取用例名
    package 格式：code_testcases.项目管理.test_project
    fullName 格式：code_testcases.项目管理.test_project#test_func
    返回：('项目管理', '项目列表加载')
    """
    module = ''

    # 优先从 package 提取（更可靠）
    if package:
        parts = package.split('.')
        for i, part in enumerate(parts):
            if part in ('ui', 'api') and i + 1 < len(parts):
                # 确保下一个部分不是test_开头的文件名
                next_part = parts[i + 1]
                if not next_part.startswith('test_'):
                    module = next_part
                    break

    # fallback: 从 fullName 提取（去掉#后面的函数名）
    if not module and full_name:
        # 去掉函数名部分（#之后的内容）
        path_part = full_name.split('#')[0] if '#' in full_name else full_name
        parts = path_part.split('.')
        for i, part in enumerate(parts):
            if part in ('ui', 'api') and i + 1 < len(parts):
                # 确保下一个部分不是test_开头的文件名
                next_part = parts[i + 1]
                if not next_part.startswith('test_'):
                    module = next_part
                    break

    # 从 suite 名称提取用例名（去掉 test_ 前缀）
    test_name = suite_name
    if suite_name.startswith('test_'):
        test_name = suite_name.replace('test_', '', 1)

    return module or '其他', test_name


# 按模块分组统计
ui_passed_by_module = defaultdict(list)
ui_failed_by_module = defaultdict(list)
api_passed_by_module = defaultdict(list)
api_failed_by_module = defaultdict(list)

import os
DEBUG = os.environ.get('DEBUG_PARSE', '0') == '1'

for full_name, results in test_results.items():
    # 取最终状态：如果有任何一次通过，算通过
    final_status = 'passed' if any(r['status'] == 'passed' for r in results) else 'failed'

    # 提取模块名和用例名
    suite_name = results[0]['suite']
    package = results[0]['package']

    if DEBUG:
        print(f"DEBUG: fullName={full_name}")
        print(f"DEBUG: package={package}")
        print(f"DEBUG: suite={suite_name}")

    module, test_name = extract_module_and_name(full_name, package, suite_name)

    if DEBUG:
        print(f"DEBUG: extracted module={module}, test_name={test_name}")
        print("---")

    # 根据类型分类（接口用例以 test_api 开头，其余归入 UI 自动化）
    if '.api.' in f'.{package}.' or '.api.' in full_name or suite_name.startswith('test_api'):
        if final_status == 'passed':
            api_passed_by_module[module].append(test_name)
        else:
            api_failed_by_module[module].append(test_name)
    else:
        if final_status == 'passed':
            ui_passed_by_module[module].append(test_name)
        else:
            ui_failed_by_module[module].append(test_name)

# 格式化输出为飞书通知格式
def format_cases_by_module(passed_dict, failed_dict):
    """
    格式化为：
    商机管理
      ✅ 商机创建、商机编辑
      ❌ 商机删除
    """
    lines = []
    all_modules = sorted(set(list(passed_dict.keys()) + list(failed_dict.keys())))

    for module in all_modules:
        passed = passed_dict.get(module, [])
        failed = failed_dict.get(module, [])

        if not passed and not failed:
            continue

        lines.append(f"**{module}**")
        if passed:
            lines.append(f"  ✅ {'、'.join(passed)}")
        if failed:
            lines.append(f"  ❌ {'、'.join(failed)}")

    return '\n'.join(lines) if lines else '无'


# 计算统计数据
ui_passed_count = sum(len(cases) for cases in ui_passed_by_module.values())
ui_failed_count = sum(len(cases) for cases in ui_failed_by_module.values())
ui_total = ui_passed_count + ui_failed_count
ui_pass_rate = f"{(ui_passed_count/ui_total*100):.1f}%" if ui_total > 0 else "0%"

api_passed_count = sum(len(cases) for cases in api_passed_by_module.values())
api_failed_count = sum(len(cases) for cases in api_failed_by_module.values())
api_total = api_passed_count + api_failed_count
api_pass_rate = f"{(api_passed_count/api_total*100):.1f}%" if api_total > 0 else "0%"

total = ui_total + api_total
passed = ui_passed_count + api_passed_count
failed = ui_failed_count + api_failed_count
pass_rate = f"{(passed/total*100):.1f}%" if total > 0 else "0%"

# 生成飞书通知用的文本
ui_cases_text = format_cases_by_module(ui_passed_by_module, ui_failed_by_module)
api_cases_text = format_cases_by_module(api_passed_by_module, api_failed_by_module)

# 写成 shell 可 source 的格式
with open('/tmp/test_env.sh', 'w', encoding='utf-8') as f:
    f.write(f"export TEST_TOTAL={total}\n")
    f.write(f"export TEST_PASSED={passed}\n")
    f.write(f"export TEST_FAILED={failed}\n")
    f.write(f'export TEST_PASS_RATE="{pass_rate}"\n')
    f.write(f"export UI_TOTAL={ui_total}\n")
    f.write(f"export UI_PASSED={ui_passed_count}\n")
    f.write(f"export UI_FAILED={ui_failed_count}\n")
    f.write(f'export UI_PASS_RATE="{ui_pass_rate}"\n')
    f.write(f"export API_TOTAL={api_total}\n")
    f.write(f"export API_PASSED={api_passed_count}\n")
    f.write(f"export API_FAILED={api_failed_count}\n")
    f.write(f'export API_PASS_RATE="{api_pass_rate}"\n')

# 将格式化后的用例文本写入文件（因为可能包含换行和特殊字符）
with open('/tmp/ui_cases.txt', 'w', encoding='utf-8') as f:
    f.write(ui_cases_text)

with open('/tmp/api_cases.txt', 'w', encoding='utf-8') as f:
    f.write(api_cases_text)

print(f"总用例: {total}, 通过: {passed}, 失败: {failed}, 通过率: {pass_rate}")
print(f"UI自动化: {ui_total}, 通过: {ui_passed_count}, 失败: {ui_failed_count}, 通过率: {ui_pass_rate}")
print(f"接口自动化: {api_total}, 通过: {api_passed_count}, 失败: {api_failed_count}, 通过率: {api_pass_rate}")
