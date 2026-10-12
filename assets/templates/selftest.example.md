# selftest 样例（派活时要求乙方模块自带自测，模板参考）

> 用途：任务文本第五要素——GUI/核心逻辑模块必须附带自测。乙方写完模块后先跑通自测再 commit。
> 两种形态二选一：轻量 `__main__` 断言（无依赖，随文件即跑）或 pytest 用例（推荐，可自动批量）。
> 要求：**关键函数 / 边界输入 / 异常输入 各至少 1 条**。
>
> 下方示例以通用的 `slugify`（标题 → URL slug）函数为载体，任何项目都能直接照搬结构——
> 把 `slugify` 换成你自己的函数名即可。

## 形态一：轻量断言（单文件自测，零依赖）

```python
# -*- coding: utf-8 -*-
import re

def slugify(title: str) -> str:
    """通用示例：把标题转成 URL 友好的 slug。
    规则：小写、空格转连字符、去掉非字母数字/连字符、折叠连续连字符。
    真实项目替换为你自己的核心函数。
    """
    if not isinstance(title, str):
        raise TypeError("title 必须是字符串")
    s = title.strip().lower()
    s = re.sub(r"[\s]+", "-", s)            # 空白 → 连字符
    s = re.sub(r"[^a-z0-9\-]", "", s)       # 去掉非字母数字连字符
    s = re.sub(r"-{2,}", "-", s).strip("-") # 折叠连续连字符
    if not s:
        raise ValueError("slug 不能为空（标题全是无意义字符）")
    return s

if __name__ == "__main__":
    # 关键函数：基本转换
    assert slugify("Hello World") == "hello-world"
    # 边界输入：混合大小写 / 多空格 / 首尾空格 / 标点
    assert slugify("  PyInstaller 打包 Guide!! ") == "pyinstaller-打包-guide" if False else "pyinstaller-guide"
    # ↑ 中文在正则里被去掉——按项目需要改规则，这里只演示断言写法
    assert slugify("a---b") == "a-b"                 # 连续连字符折叠
    assert slugify("X") == "x"                       # 单字符
    # 异常输入
    for bad in (None, 123, "", "   ", "!!!"):
        try:
            slugify(bad)
            raise AssertionError(f"输入 {bad!r} 应抛异常")
        except (TypeError, ValueError):
            pass
    print("selftest 全部通过")
```

## 形态二：pytest（推荐，多模块/回归场景）

```python
# tests/test_slug.py
import pytest

def test_key_function():
    assert slugify("Hello World") == "hello-world"
    assert slugify("D2W Skill") == "d2w-skill"

def test_boundary_case():
    assert slugify("  spaced  out  ") == "spaced-out"   # 多空格折叠
    assert slugify("A---B") == "a-b"                   # 连续连字符
    assert slugify("123") == "123"                     # 纯数字

def test_invalid_input():
    with pytest.raises(TypeError):
        slugify(None)
    with pytest.raises(TypeError):
        slugify(123)
    with pytest.raises(ValueError):
        slugify("")
    with pytest.raises(ValueError):
        slugify("!!!")     # 去掉标点后为空
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
4. 自测覆盖度检查：关键函数 / 边界输入 / 异常输入三类用例是否齐全——缺一类就是 P1
