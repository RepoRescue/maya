# 升级报告

## 基本信息

| 项目 | 值 |
|------|-----|
| 仓库名 | maya |
| 升级时间 | 2026-03-14 |
| 升级状态 | ✅ 成功 |

## Python 版本

| 升级前 | 升级后 |
|--------|--------|
| >=2.7, >=3.6 | >=3.13 |

## 依赖变更

| 依赖 | 升级前 | 升级后 |
|------|--------|--------|
| humanize | (无版本限制) | >=4.15.0 |
| pytz | (无版本限制) | >=2026.1 |
| dateparser | >=0.7.0 | >=1.3.0 |
| tzlocal | (无版本限制) | >=5.3.1 |
| pendulum | >=2.0.2 | >=3.2.0 |
| snaptime | (无版本限制) | >=0.2.4 |
| freezegun | (无版本限制) | >=1.5.5 |
| pytest | (无版本限制) | >=9.0.2 |
| pytest-mock | (无版本限制) | >=3.15.1 |

## 代码修改

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| src/maya/core.py:261-263 | API 迁移 | 将 `datetime.utcfromtimestamp()` 替换为 `datetime.fromtimestamp(tz=timezone.utc)` |
| src/maya/core.py:364-386 | 时区处理修复 | 修复 `slang_date()` 方法的时区转换问题，使用本地时区进行 humanize |
| src/maya/core.py:720-775 | 相对时间解析修复 | 修复 `when()` 函数对 "midnight" 等相对时间的解析逻辑 |
| src/maya/core.py:808-820 | ISO8601 解析增强 | 添加对特殊 ISO8601 格式（如 `2016T14`）的支持，使用 `datetime.fromisoformat()` 作为 fallback |
| setup.py:11-24 | Python 版本声明 | 移除 Python 2.7 和 3.6 支持，添加 Python 3.13 |
| setup.py:27-34 | 依赖版本锁定 | 更新所有依赖到最新版本 |
| setup.py:71-93 | Python 版本要求 | 添加 `python_requires=">=3.13"` |

## 测试结果

| 测试类型 | 结果 |
|----------|------|
| 总测试数 | 426 个 |
| 通过 | 426 passed |
| 失败 | 0 failed |
| 警告 | 1 warning (测试代码中的 utcfromtimestamp 使用) |

| 升级前 | 升级后 |
|--------|--------|
| N/A (旧环境测试失败) | ✅ 426 passed, 0 failed |

## 主要修复问题

1. **datetime.utcfromtimestamp() 弃用**
   - Python 3.12+ 弃用此 API
   - 替换为 `datetime.fromtimestamp(tz=timezone.utc)`

2. **slang_date() 时区问题**
   - humanize.naturaldate() 使用本地时区比较日期
   - 修复为先转换到本地时区再调用 humanize

3. **midnight 解析问题**
   - dateparser 对 "midnight" 的解析在跨日时有歧义
   - 添加特殊处理，确保返回当前日期的 midnight

4. **ISO8601 特殊格式支持**
   - pendulum 不支持某些简化的 ISO8601 格式（如 `2016T14`）
   - 添加 fallback 到 `datetime.fromisoformat()` 和手动解析

5. **Pendulum 3.x 升级**
   - 从 pendulum 2.x 升级到 3.x
   - API 兼容性良好，无需修改代码

## 备注

所有测试通过，代码已完全兼容 Python 3.13 + 最新依赖。
