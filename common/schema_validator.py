"""
API响应模板匹配校验器

断言文件就是期望的响应体，写具体值表示精确匹配，写 "*" 表示任意值都能过。

规则：
  - "*"          匹配任意值（包括 null、数组、对象）
  - 具体值        精确匹配（如 "200"、true、123）
  - ["*"]        匹配任意数组
  - {"*": "*"}   匹配任意对象
"""
import json
import logging

logger = logging.getLogger("qa_test")


def match_template(expected, actual, path="$"):
    """递归比较模板和实际响应，返回不匹配的错误列表"""
    errors = []

    # 通配符：任意值都通过
    if expected == "*":
        return errors

    # 类型不同直接报错（null 特殊处理）
    if expected is None:
        if actual is not None:
            errors.append(f"{path}: 期望 null, 实际 {json.dumps(actual, ensure_ascii=False)}")
        return errors

    # 字典匹配
    if isinstance(expected, dict):
        # {"*": "*"} 通配任意对象
        if expected == {"*": "*"}:
            if not isinstance(actual, dict):
                errors.append(f"{path}: 期望对象, 实际 {type(actual).__name__}")
            return errors

        if not isinstance(actual, dict):
            errors.append(f"{path}: 期望对象, 实际 {type(actual).__name__}")
            return errors

        # 逐字段校验（只校验模板中定义的字段）
        for key, exp_val in expected.items():
            if key not in actual:
                errors.append(f"{path}.{key}: 字段不存在")
            else:
                errors.extend(match_template(exp_val, actual[key], f"{path}.{key}"))
        return errors

    # 数组匹配
    if isinstance(expected, list):
        # ["*"] 通配任意数组
        if expected == ["*"]:
            if not isinstance(actual, list):
                errors.append(f"{path}: 期望数组, 实际 {type(actual).__name__}")
            return errors

        if not isinstance(actual, list):
            errors.append(f"{path}: 期望数组, 实际 {type(actual).__name__}")
            return errors

        # 逐元素校验
        for i, exp_item in enumerate(expected):
            if i >= len(actual):
                errors.append(f"{path}[{i}]: 数组元素不存在")
            else:
                errors.extend(match_template(exp_item, actual[i], f"{path}[{i}]"))
        return errors

    # 精确值匹配
    if expected != actual:
        errors.append(
            f"{path}: 期望 {json.dumps(expected, ensure_ascii=False)}, "
            f"实际 {json.dumps(actual, ensure_ascii=False)}"
        )

    return errors
