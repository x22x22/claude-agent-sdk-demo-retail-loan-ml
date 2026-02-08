# Agent 配置文件

本目录包含 claude-agent-sdk 的 Agent 配置文件（Markdown 格式）。

## 文件说明

| 文件 | 说明 | 行数 |
|------|------|------|
| `main_agent.md` | 主 Agent 配置（系统提示词 + 工具列表 + 子 Agent） | ~100 |
| `data_agent.md` | 数据子 Agent（负责数据加载和概况查询） | ~60 |
| `training_agent.md` | 训练子 Agent（负责模型训练） | ~85 |
| `recommendation_agent.md` | 推荐子 Agent（负责推荐和预测） | ~150 |

## 配置格式

所有配置文件使用 **YAML Frontmatter + Markdown** 格式：

```markdown
---
name: agent_name
description: Agent 描述
model: sonnet
tools:
  - tool1
  - tool2
---

# Agent 标题

Agent 的系统提示词内容（Markdown 格式）...
```

### Frontmatter 字段说明

- `name`: Agent 名称（必需）
- `description`: Agent 简短描述（必需）
- `model`: 使用的模型（如 sonnet, haiku 等）
- `tools`: 允许使用的工具列表
- `allowed_tools`: 允许的工具（主 Agent）
- `disallowed_tools`: 禁用的工具（主 Agent）
- `agents`: 子 Agent 列表（主 Agent）

### Markdown 正文

Frontmatter 之后的 Markdown 内容作为 Agent 的 **system_prompt**（系统提示词）。

可以使用：
- 标题（# ## ###）
- 列表（- * 1.）
- 表格
- 代码块
- 粗体/斜体

## 使用方式

### 方式一：SDK 原生支持（推荐）

如果 `claude-agent-sdk` 支持从 Markdown 文件加载配置：

```python
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

options = ClaudeAgentOptions(
    agent_file="path/to/main_agent.md",  # 主 Agent 配置
    agents_dir="path/to/agents/",         # 子 Agent 配置目录
    # ... 其他配置
)
```

### 方式二：手动解析（兼容方案）

如果 SDK 不支持，可以自己解析 Markdown：

```python
import yaml
from pathlib import Path

def load_agent_from_md(md_file: Path) -> dict:
    """从 MD 文件加载 Agent 配置"""
    content = md_file.read_text(encoding="utf-8")
    
    # 分离 frontmatter 和正文
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            metadata = yaml.safe_load(parts[1])
            prompt = parts[2].strip()
            return {
                "metadata": metadata,
                "prompt": prompt
            }
    
    return {"metadata": {}, "prompt": content}

# 使用示例
agent_config = load_agent_from_md(Path("main_agent.md"))
system_prompt = agent_config["prompt"]
tools = agent_config["metadata"].get("tools", [])
```

## 修改指南

### 修改提示词

直接编辑 Markdown 文件即可，无需修改 Python 代码。

示例：要修改主 Agent 的行为
```bash
vim .github/agents/main_agent.md
# 编辑系统提示词...
# 保存并重启应用
```

### 添加新工具

在 Frontmatter 的 `tools` 列表中添加：

```yaml
---
tools:
  - existing_tool
  - new_tool  # 新增
---
```

### 添加新子 Agent

1. 创建新的 MD 文件（如 `risk_agent.md`）
2. 在主 Agent 的 `agents` 列表中添加
3. 重启应用

### 版本管理

配置文件独立版本控制：
- 提示词修改：清晰的文本 diff
- 回滚方便：`git checkout old_version -- main_agent.md`
- 分支隔离：不同分支可以有不同的 Agent 配置

## 相关文档

- 完整分析：`/SDK配置外部化分析报告.md`
- 快速参考：`/SDK配置外部化快速参考.md`
- 架构说明：`/ARCHITECTURE.md`
