#!/usr/bin/env python3
"""测试 _parse_arguments 方法"""
import sys
sys.path.insert(0, '.')

from src.api.tool_executor import ToolExecutor

def test_parse_arguments():
    executor = ToolExecutor()
    
    # 测试用例
    test_cases = [
        # (输入, 期望输出类型, 描述)
        ('{"key": "value"}', dict, "正常 JSON 对象"),
        ('["a", "b"]', list, "正常 JSON 数组"),
        ('"plain string"', str, "普通字符串"),
        ('123', int, "整数"),
        ('true', bool, "布尔值"),
        # 转义 JSON 字符串：参数是字符串化的 JSON
        ('\"{\\"key\\": \\"value\\"}\"', dict, "双重转义的 JSON 字符串"),
        ('\"[1, 2, 3]\"', list, "字符串化的 JSON 数组"),
        # 单引号包裹的字符串
        ("'{\"key\": \"value\"}'", dict, "单引号包裹的 JSON 字符串"),
        ("'plain'", str, "单引号字符串"),
        # 混合情况
        ('{"nested": {"inner": "value"}}', dict, "嵌套 JSON"),
        ('  {"trim": "me"}  ', dict, "带有空格的 JSON"),
    ]
    
    for input_str, expected_type, description in test_cases:
        try:
            result = executor._parse_arguments(input_str)
            if isinstance(result, expected_type):
                print(f"✓ {description}: 输入={repr(input_str)} 结果={repr(result)}")
            else:
                print(f"✗ {description}: 期望类型 {expected_type}，实际类型 {type(result)} 值 {repr(result)}")
        except Exception as e:
            print(f"✗ {description}: 异常 {e}")

if __name__ == '__main__':
    test_parse_arguments()