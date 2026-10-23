"""
API响应断言工具 — 基于模板匹配

断言文件是期望的响应JSON，写具体值精确匹配，写 "*" 通配任意值。
"""
import os
import json
import inspect
import allure
from common.schema_validator import match_template


def assert_with_schema(resp, schema_file=None):
    """根据模板文件断言接口响应

    Args:
        resp: 接口响应字典
        schema_file: 断言文件名（如 "健康检查.json"），不传则自动推导

    自动推导规则:
        test_api_健康检查.py -> assertions/健康检查.json
    """
    caller_frame = inspect.stack()[1]
    caller_dir = os.path.dirname(caller_frame.filename)

    if schema_file is None:
        base_name = os.path.basename(caller_frame.filename)
        schema_file = base_name.replace("test_api_", "").replace(".py", ".json")

    schema_path = os.path.join(caller_dir, "assertions", schema_file)
    assert os.path.exists(schema_path), f"断言文件不存在: {schema_path}"

    with open(schema_path, "r", encoding="utf-8") as f:
        template = json.load(f)

    errors = match_template(template, resp)

    if errors:
        error_msg = "\n".join(f"  - {e}" for e in errors)
        allure.attach(
            body=f"断言失败:\n{error_msg}\n\n实际响应:\n{json.dumps(resp, ensure_ascii=False, indent=2)}",
            name="响应断言失败详情",
            attachment_type=allure.attachment_type.TEXT,
        )
        assert False, f"接口响应不符合预期:\n{error_msg}"
