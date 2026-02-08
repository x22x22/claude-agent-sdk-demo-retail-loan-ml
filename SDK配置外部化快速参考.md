# SDK 配置外部化快速参考

> 本文档总结 SDK 配置外部化方案的关键要点，完整分析见《SDK配置外部化分析报告.md》

## 一分钟了解

### 问题
当前项目将 Agent 配置硬编码在 Python 文件中，导致：
- 代码臃肿（180行配置代码）
- 修改提示词需要编辑 Python
- 非技术人员无法参与优化

### 方案
将配置转换为 Markdown 文件（`.github/agents/*.md`），实现：
- ✅ 代码减少 76%（180行 → 44行）
- ✅ 提示词独立管理，易于修改
- ✅ 非技术人员可直接编辑 MD 文件

## 代码对比

### 当前方案（硬编码）

**agents/definitions.py** - 64 行
```python
MAIN_SYSTEM_PROMPT = """你是零售贷款智能运营助手..."""  # 25行

def build_sub_agent_definitions():
    return {
        "data_agent": AgentDefinition(
            description="...",
            prompt="""...""",  # 每个子 Agent 10行
            tools=[...],
            model="sonnet",
        ),
        # ... 另外2个子 Agent
    }
```

**agents/runner.py** - 44 行
```python
from agents.definitions import MAIN_SYSTEM_PROMPT, build_sub_agent_definitions

options_dict = {
    "system_prompt": MAIN_SYSTEM_PROMPT,
    "allowed_tools": ["Read", "Grep", ...],
    "disallowed_tools": ["Write", "Edit"],
}
sub_agents = build_sub_agent_definitions()
if sub_agents:
    options_dict["agents"] = sub_agents
```

### 外部化方案（Markdown）

**目录结构**
```
.github/
└── agents/
    ├── main_agent.md              # 主 Agent（60行）
    ├── data_agent.md              # 数据子 Agent（30行）
    ├── training_agent.md          # 训练子 Agent（35行）
    └── recommendation_agent.md    # 推荐子 Agent（40行）
```

**agents/definitions.py** - 8 行（减少 88%）
```python
"""从 .github/agents/ 目录读取配置"""
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent.parent / ".github" / "agents"
MAIN_AGENT_FILE = AGENTS_DIR / "main_agent.md"
```

**agents/runner.py** - 36 行（减少 18%）
```python
# 无需导入 MAIN_SYSTEM_PROMPT 和 build_sub_agent_definitions()

agents_dir = PROJECT_ROOT / ".github" / "agents"
main_agent_path = agents_dir / "main_agent.md"

options_dict = {
    **agent_kw,
    "agent_file": str(main_agent_path),  # SDK 自动读取
    "agents_dir": str(agents_dir),       # SDK 自动扫描子 Agent
}
```

## 配置文件示例

### .github/agents/main_agent.md

```markdown
---
name: main_agent
description: 零售贷款智能运营主助手
model: sonnet
allowed_tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Task
  - mcp__loan_agent__load_data
  - mcp__loan_agent__train_models
  - mcp__loan_agent__recommend
disallowed_tools:
  - Write
  - Edit
agents:
  - data_agent
  - training_agent
  - recommendation_agent
---

# 零售贷款智能运营助手

你是零售贷款智能运营助手。所有回复必须使用中文。

## 工作方式

你可以通过两种方式完成用户请求：

### 方式一：直接使用 MCP 工具
（工具列表和说明...）

### 方式二：通过 Task 调用子 Agent
（子 Agent 说明...）
```

### .github/agents/data_agent.md

```markdown
---
name: data_agent
description: 负责数据加载与数据概况查询
model: sonnet
tools:
  - mcp__loan_agent__load_data
  - mcp__loan_agent__get_data_summary
---

# 数据助手

你是零售贷款场景的数据助手。你只能使用 load_data、get_data_summary 两个工具。

## 任务范围
- 加载数据
- 查看数据概况

## 工作要求
请根据请求调用相应工具，并用中文简要汇总结果。
```

## 收益对比表

| 维度 | 当前方案 | 外部化方案 | 改进 |
|------|---------|-----------|------|
| 代码行数 | 180 | 44 | **-76%** |
| 配置文件行数 | 64 | 8 | **-88%** |
| 提示词修改 | 编辑 Python | 编辑 MD | **更简单** |
| 技术门槛 | 需懂 Python | 只需懂 Markdown | **降低** |
| 版本对比 | 代码 diff | 文本 diff | **更清晰** |
| 协作友好度 | 仅开发者 | 所有人 | **提升** |

## 实施步骤（2小时）

### 步骤 1：创建配置文件（45分钟）
```bash
mkdir -p .github/agents
# 创建 4 个 MD 文件，内容见《SDK配置外部化分析报告.md》第四章
```

### 步骤 2：修改 Python 代码（30分钟）
- 简化 `agents/definitions.py` 到 8 行
- 修改 `agents/runner.py` 使用 `agent_file` 和 `agents_dir` 参数

### 步骤 3：测试验证（45分钟）
```bash
# 测试主 Agent
python -m scripts.run_agent

# 测试 Web UI
python main.py
```

## 兼容性方案

如果 SDK 暂不支持 Markdown 配置，可以自己解析：

```python
def load_prompt_from_md(agent_name: str) -> str:
    """从 MD 文件加载提示词"""
    md_file = AGENTS_DIR / f"{agent_name}.md"
    if md_file.exists():
        content = md_file.read_text(encoding="utf-8")
        # 分离 frontmatter 和正文
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return parts[2].strip()
    return ""
```

这样即使 SDK 不支持，也能实现配置外部化，代码仍然简洁。

## 风险与应对

| 风险 | 概率 | 应对 |
|------|------|------|
| SDK 不支持 Markdown | 中 | 使用兼容性方案 |
| 配置解析失败 | 低 | 添加错误处理 |
| 功能测试不通过 | 低 | 保留原代码参考 |

## 下一步

1. **立即可做**：阅读完整报告《SDK配置外部化分析报告.md》
2. **验证 SDK**：确认是否原生支持 Markdown 配置
3. **开始实施**：从主 Agent 外部化开始（最低风险）
4. **逐步完善**：子 Agent 外部化 → 优化配置管理

---

**完整分析**：见同目录下《SDK配置外部化分析报告.md》（718行详细分析）  
**相关文档**：《Agent业务流程控制分析报告.md》（流程控制分析）
