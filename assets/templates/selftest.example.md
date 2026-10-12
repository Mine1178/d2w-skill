# selftest 样例（派活时要求乙方模块自带自测，模板参考）

> 用途：任务文本第五要素——GUI/核心逻辑模块必须附带自测。乙方写完模块后先跑通自测再 commit。
> 两种形态二选一：轻量 `__main__` 断言（无依赖，随文件即跑）或 pytest 用例（推荐，可自动批量）。
> 要求：**关键函数 / 边界输入 / 异常输入 各至少 1 条**。

## 形态一：轻量断言（单文件自测，零依赖）

```python
# -*- coding: utf-8 -*-
def translate_word(word: str) -> str:
    """示例核心函数：单词查译（假实现，真实项目替换为引擎调用）"""
    if not isinstance(word, str) or not word.strip():
        raise ValueError("word 不能为空")
    table = {"hello": "你好", "world": "世界"}
    return table.get(word.strip().lower(), word)

if __name__ == "__main__":
    # 关键函数
    assert translate_word("hello") == "你好"
    # 边界输入
    assert translate_word("WORLD") == "世界"        # 大小写归一
    assert translate_word("xyz_not_exist") == "xyz_not_exist"  # 未收录回退原词
    # 异常输入
    try:
        translate_word("  ")
        raise AssertionError("空输入应抛 ValueError")
    except ValueError:
        pass
    print("selftest 全部通过")
```

## 形态二：pytest（推荐，多模块/回归场景）

```python
# tests/test_translator.py
import pytest

def test_key_function():
    assert translate_word("hello") == "你好"

def test_boundary_case():
    assert translate_word("HELLO") == "你好"   # 大小写
    assert translate_word("a") == "a"          # 单字符回退

def test_invalid_input():
    with pytest.raises(ValueError):
        translate_word("")
    with pytest.raises(ValueError):
        translate_word(None)
```

运行：
```bash
python -m pytest tests/ -q        # 项目有 pytest
python module.py                   # 轻量断言模式
```

## 审核方怎么用

1. 派活文本要求"写完先跑 selftest 通过再 commit"
2. 审核时直接运行：`python -m py_compile <模块>`（语法）→ `python <模块>` 或 `python -m pytest tests/ -q`（行为）
3. 结果分类：**环境缺依赖**（ModuleNotFoundError 等）≠ **逻辑 bug**（AssertionError 断言失败）——前者装依赖重跑，后者报 P0/P1
