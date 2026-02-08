# Agent 业务流程控制分析报告

## 项目概述

本项目是一个**基于 claude-agent-sdk 的零售贷款智能运营系统**，通过智能 Agent 与用户进行自然语言交互，实现数据加载、模型训练、个性化推荐等业务功能。

项目的核心问题是：**Agent 的业务流程是在代码层面控制的，还是在提示词（Prompt）里控制的？**

**结论：本项目采用了「提示词控制为主 + 代码辅助为辅」的混合模式，业务流程的决策权主要由 LLM 通过提示词理解并执行，代码层面仅提供工具能力和架构支撑。**

---

## 一、核心架构分析

### 1.1 项目结构

```
claude-agent-sdk-demo-retail-loan-ml/
├── agents/                    # Agent 定义层
│   ├── definitions.py        # 主 Agent 和子 Agent 的提示词定义
│   └── runner.py             # Agent 运行入口（SDK 调用）
├── tools/                     # 工具层
│   └── loan_agent_tools.py   # MCP 工具实现（6个业务工具）
├── core/                      # 配置层
│   └── config.py             # 模型后端配置
├── app/                       # 业务逻辑层
│   ├── data_prep.py          # 数据准备
│   └── model_training.py     # 模型训练
├── scripts/                   # 入口脚本
│   └── run_agent.py          # 命令行对话入口
└── ui/                        # Web 界面
    └── app.py                # Gradio UI（不涉及 Agent）
```

### 1.2 关键技术栈

- **claude-agent-sdk**：Agent 编排框架，支持多种 LLM 后端（Anthropic Claude、Ollama 等）
- **MCP (Model Context Protocol)**：工具协议，用于 Agent 调用业务功能
- **自然语言驱动**：用户通过对话实现业务操作

---

## 二、业务流程控制方式深度剖析

### 2.1 提示词控制（主导方式）

#### 2.1.1 主 Agent 的提示词设计

位置：`agents/definitions.py` → `MAIN_SYSTEM_PROMPT`

```python
MAIN_SYSTEM_PROMPT = """你是零售贷款智能运营助手。所有回复必须使用中文。

你可以通过两种方式完成用户请求：

【方式一】直接使用 MCP 工具：load_data、get_data_summary、train_models、recommend、predict_propensity、similar_items。

【方式二】通过 Task 调用子 Agent（适合多步骤或需要专项分析的场景）。调用 Task 时必须传入：
- subagent_type：取 data_agent、training_agent、recommendation_agent 之一
- description：简短任务描述（中文）
- prompt：发给该子 Agent 的具体指令（中文）

子 Agent 说明：
- data_agent：负责数据加载与概况查询。可完成「加载数据」「查看数据概况」等。
- training_agent：负责模型训练。可完成「训练贷款意愿模型与推荐模型」。
- recommendation_agent：负责推荐与意愿预测。可完成「为某客户推荐产品」「预测某客户对某产品的意愿」「查找相似产品」。

工作流程建议：用户说「加载数据」时可直接调用 load_data 或 Task(data_agent)；说「训练模型」时调用 train_models 或 Task(training_agent)；说「推荐」或「预测意愿」时调用 recommend/predict_propensity/similar_items 或 Task(recommendation_agent)。若用户未指定客户ID或产品ID，可先调用 get_data_summary 了解数据规模并提示用户提供有效的 user_id 或 item_id。

回复时请先简要说明你执行了哪些工具或调用了哪个子 Agent，再给出结果摘要。"""
```

**关键分析：**

1. **角色定义**：通过提示词明确 Agent 的身份是"零售贷款智能运营助手"
2. **工作方式**：提示词详细说明了两种工作方式（直接调工具 vs 委派子 Agent）
3. **决策逻辑**：提示词提供了"工作流程建议"，但**最终决策权在 LLM**
4. **参数处理**：提示词建议"若用户未指定ID，先调用 get_data_summary"，这是**典型的提示词控制**

#### 2.1.2 子 Agent 的提示词设计

位置：`agents/definitions.py` → `build_sub_agent_definitions()`

**数据子 Agent (data_agent)**
```python
AgentDefinition(
    description="负责数据加载与数据概况查询。用于执行加载示例数据、查看当前交互数/客户数/产品数等。",
    prompt="""你是零售贷款场景的数据助手。你只能使用 load_data、get_data_summary 两个工具。
用户可能要求：加载数据、查看数据概况、看看当前有多少条数据等。请根据请求调用相应工具，并用中文简要汇总结果。""",
    tools=["mcp__loan_agent__load_data", "mcp__loan_agent__get_data_summary"],
    model="sonnet",
)
```

**训练子 Agent (training_agent)**
```python
AgentDefinition(
    description="负责贷款意愿模型与推荐模型的训练。用于执行训练流程并汇报指标。",
    prompt="""你是零售贷款场景的模型训练助手。你只能使用 train_models 工具。
用户可能要求：训练模型、开始训练、训练意愿模型和推荐模型等。调用 train_models 后，用中文汇总训练结果（如 ROC-AUC、准确率等）。若未加载数据，工具会先自动加载再训练。""",
    tools=["mcp__loan_agent__train_models"],
    model="sonnet",
)
```

**推荐子 Agent (recommendation_agent)**
```python
AgentDefinition(
    description="负责个性化推荐、贷款意愿预测、相似产品查询。需要 user_id 或 item_id 时由主 Agent 或用户提供。",
    prompt="""你是零售贷款场景的推荐与预测助手。你只能使用 recommend、predict_propensity、similar_items 三个工具。
用户可能要求：为某客户推荐产品（需 user_id，可选 top_k）、预测某客户对某产品的意愿（需 user_id、item_id）、查找相似产品（需 item_id）。请根据请求调用相应工具并传入必要参数，用中文汇总结果。若缺少 user_id 或 item_id，请说明并建议先查数据概况。""",
    tools=["mcp__loan_agent__recommend", "mcp__loan_agent__predict_propensity", "mcp__loan_agent__similar_items"],
    model="sonnet",
)
```

**关键分析：**

1. **权限控制**：通过 `tools` 参数限制每个子 Agent 只能使用特定工具
2. **职责划分**：通过 `description` 和 `prompt` 明确各子 Agent 的职责范围
3. **错误处理**：提示词中包含"若缺少参数，请说明并建议"等引导性语句
4. **自然语言指导**：完全依赖提示词描述业务场景和预期行为

### 2.2 代码控制（辅助方式）

#### 2.2.1 工具能力封装

位置：`tools/loan_agent_tools.py`

代码层面定义了 6 个 MCP 工具：

```python
# 1. 加载数据
async def tool_load_data(args: dict) -> dict:
    """加载示例数据（MovieLens 100k 转贷款场景）。无需参数。"""
    datasets = _ensure_datasets()
    # ... 返回加载结果

# 2. 查看数据概况
async def tool_get_data_summary(args: dict) -> dict:
    """查看当前数据概况（交互数、客户数、产品数）。若无数据会先加载。"""
    # ... 返回数据统计

# 3. 训练模型
async def tool_train_models(args: dict) -> dict:
    """基于当前已加载数据训练贷款意愿模型与推荐模型。无需参数。若未加载数据会先自动加载。"""
    propensity, recommender = _ensure_models()
    # ... 返回训练指标

# 4. 个性化推荐
async def tool_recommend(args: dict) -> dict:
    """为指定客户做个性化贷款推荐。参数：user_id（客户ID，字符串），top_k（推荐数量，默认5）。"""
    user_id = str(args.get("user_id", ""))
    top_k = int(args.get("top_k", 5))
    # ... 返回推荐结果

# 5. 预测意愿
async def tool_predict_propensity(args: dict) -> dict:
    """预测某客户对某贷款产品的申请意愿概率。参数：user_id（客户ID），item_id（产品ID）。"""
    # ... 返回预测概率

# 6. 相似产品
async def tool_similar_items(args: dict) -> dict:
    """查找与某贷款产品相似的其他产品。参数：item_id（产品ID），top_k（数量，默认5）。"""
    # ... 返回相似产品列表
```

**关键分析：**

1. **工具是能力的提供者**：代码定义了"能做什么"，但不决定"什么时候做"
2. **参数验证**：代码层面进行基本的参数检查（如 `if not user_id`）
3. **容错处理**：如 `_ensure_datasets()` 会在数据未加载时自动加载
4. **返回标准化**：所有工具返回统一的字典格式 `{"content": [{"type": "text", "text": ...}]}`

#### 2.2.2 工具注册与服务构建

```python
def build_loan_agent_mcp_server():
    """创建零售贷款 MCP 服务，供 ClaudeAgentOptions.mcp_servers 使用。"""
    from claude_agent_sdk import tool, create_sdk_mcp_server
    
    # 使用装饰器注册工具
    load_data_tool = tool(
        "load_data",
        "加载示例贷款场景数据（MovieLens 100k 转贷款）。无参数。",
        {},
    )(tool_load_data)
    
    # ... 注册其他工具
    
    return create_sdk_mcp_server(
        name="loan_agent",
        version="1.0.0",
        tools=[load_data_tool, train_tool, summary_tool, recommend_tool, predict_tool, similar_tool],
    )
```

**关键分析：**

1. **声明式注册**：通过 `@tool` 装饰器声明工具元数据（名称、描述、参数）
2. **工具描述**：描述文本会被 LLM 读取，用于理解工具用途
3. **服务封装**：将多个工具打包成一个 MCP Server

#### 2.2.3 Agent 运行框架

位置：`agents/runner.py`

```python
async def run_agent(user_message: str) -> AsyncIterator[Any]:
    """根据 core.config.LLM_BACKEND 使用对应后端（ollama / anthropic 等）执行对话"""
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
    
    # 1. 构建配置
    agent_kw = build_agent_options_kwargs(cwd=cwd)
    
    # 2. 设置允许的工具
    allowed = ["Read", "Grep", "Glob", "Bash", "Task"] + get_loan_agent_allowed_tools()
    
    # 3. 构建 MCP Server
    mcp_server = build_loan_agent_mcp_server()
    
    # 4. 构建子 Agent
    sub_agents = build_sub_agent_definitions()
    
    # 5. 创建 Agent Options
    options = ClaudeAgentOptions(
        **agent_kw,
        system_prompt=MAIN_SYSTEM_PROMPT,  # 提示词注入
        allowed_tools=allowed,
        disallowed_tools=["Write", "Edit"],
        mcp_servers={"loan_agent": mcp_server},
        agents=sub_agents,
    )
    
    # 6. 执行对话
    async with ClaudeSDKClient(options=options) as client:
        await client.connect()
        await client.query(user_message, session_id="default")
        async for message in client.receive_response():
            yield message
```

**关键分析：**

1. **框架搭建**：代码负责搭建 Agent 运行环境
2. **配置注入**：将提示词、工具、子 Agent 等配置传入 SDK
3. **执行委托**：实际的推理和决策由 `ClaudeSDKClient` 内部的 LLM 完成
4. **流式输出**：通过异步生成器流式返回结果

---

## 三、业务流程实例分析

### 3.1 场景一：用户说"加载数据"

**提示词的作用：**
1. 主 Agent 的提示词告诉 LLM："用户说「加载数据」时可直接调用 load_data 或 Task(data_agent)"
2. LLM 理解用户意图，决定调用 `load_data` 工具
3. LLM 构造工具调用请求：`{"name": "load_data", "args": {}}`

**代码的作用：**
1. `tool_load_data` 函数被触发
2. 执行 `_ensure_datasets()`，调用 `app.data_prep.prepare_datasets()`
3. 返回结果给 LLM
4. LLM 根据返回内容生成用户友好的回复

**决策权在谁？** → **提示词（LLM）**
- 是否调用工具：LLM 决定
- 调用哪个工具：LLM 决定
- 何时调用：LLM 决定

### 3.2 场景二：用户说"加载数据，然后训练模型"

**提示词的作用：**
1. LLM 理解这是一个**多步骤**请求
2. 根据提示词中的"工作流程建议"，LLM 决定：
   - 第一步：调用 `load_data`
   - 第二步：调用 `train_models`
3. LLM **自主规划**执行顺序

**代码的作用：**
1. `tool_train_models` 中有容错代码：`_ensure_models()` 会检查数据是否加载
2. 即使 LLM 只调用了 `train_models`，代码也会自动加载数据

**决策权在谁？** → **提示词为主，代码为辅**
- 流程规划：LLM 决定（提示词引导）
- 容错处理：代码兜底（但不控制主流程）

### 3.3 场景三：用户说"为客户 1 推荐产品"

**提示词的作用：**
1. 主 Agent 的提示词建议："说「推荐」时调用 recommend/predict_propensity/similar_items 或 Task(recommendation_agent)"
2. LLM 提取参数：`user_id = "1"`
3. LLM 决定：直接调用 `recommend` 工具还是委派给 `recommendation_agent`

**代码的作用：**
1. `tool_recommend` 接收参数：`{"user_id": "1", "top_k": 5}`
2. 执行推荐算法
3. 返回推荐列表

**决策权在谁？** → **提示词（LLM）**
- 参数提取：LLM 完成（从自然语言中提取 `user_id`）
- 工具选择：LLM 决定
- 错误处理：代码检查（如用户不存在），但由 LLM 决定如何响应用户

### 3.4 场景四：用户说"训练模型"但未加载数据

**提示词的作用：**
1. 提示词中有说明："若未加载数据，工具会先自动加载再训练"
2. 但这是**给 LLM 的提示**，让 LLM 知道可以直接调用 `train_models`

**代码的作用：**
1. `_ensure_models()` 检查数据状态
2. 若未加载，自动调用 `prepare_datasets()`
3. 然后执行训练

**决策权在谁？** → **混合模式**
- 流程决策：LLM 决定（可以直接调用 `train_models`）
- 依赖处理：代码自动处理（无需 LLM 干预）

---

## 四、提示词 vs 代码：分工原则

### 4.1 提示词负责的部分

| 职责 | 体现 | 示例 |
|------|------|------|
| **意图理解** | 将自然语言转换为工具调用 | "加载数据" → `load_data()` |
| **流程规划** | 多步骤任务的执行顺序 | "加载数据，然后训练模型" → 先 `load_data`，后 `train_models` |
| **参数提取** | 从对话中提取工具参数 | "为客户 1 推荐" → `user_id="1"` |
| **容错沟通** | 缺少参数时与用户交互 | "请提供客户ID" |
| **结果总结** | 将工具返回转换为友好回复 | 数字 → "成功加载 10万条数据" |
| **子任务委派** | 决定是否调用子 Agent | 复杂任务 → `Task(data_agent)` |

### 4.2 代码负责的部分

| 职责 | 体现 | 示例 |
|------|------|------|
| **工具实现** | 实际的业务逻辑 | 数据加载、模型训练算法 |
| **参数验证** | 检查参数合法性 | `if not user_id: return error` |
| **容错兜底** | 自动处理依赖关系 | `_ensure_datasets()` |
| **状态管理** | 管理数据和模型状态 | `_state` 字典 |
| **返回格式化** | 标准化工具返回格式 | `{"content": [...]}` |
| **架构搭建** | SDK 初始化、配置注入 | `ClaudeAgentOptions(...)` |

### 4.3 决策权归属总结

```
用户输入 (自然语言)
    ↓
提示词控制层 (LLM)
    ├─ 理解意图
    ├─ 规划流程
    ├─ 选择工具
    ├─ 提取参数
    └─ 生成调用
         ↓
代码执行层
    ├─ 参数验证
    ├─ 业务逻辑
    ├─ 容错处理
    └─ 返回结果
         ↓
提示词控制层 (LLM)
    ├─ 结果理解
    ├─ 内容总结
    └─ 生成回复
         ↓
用户输出 (自然语言)
```

**核心结论**：
- **决策权**：70% 提示词（LLM） + 30% 代码
- **业务流程控制**：提示词主导
- **业务逻辑实现**：代码主导

---

## 五、为什么选择提示词控制？

### 5.1 灵活性

**提示词方式：**
```
用户："先看看有多少数据，如果少于 1000 条就重新加载，然后训练模型"
```
- LLM 可以理解复杂的条件逻辑
- 无需修改代码即可支持新的业务流程

**代码方式（假设）：**
```python
if dataset_size < 1000:
    load_data()
train_models()
```
- 需要为每个业务场景编写代码
- 缺乏灵活性

### 5.2 可维护性

**提示词方式：**
- 修改业务流程：更新 `MAIN_SYSTEM_PROMPT`
- 新增业务场景：调整提示词描述
- 不需要重新编译或部署

**代码方式：**
- 新增流程分支需要修改代码
- 增加测试成本
- 部署周期长

### 5.3 用户体验

**提示词控制的优势：**
1. **自然交互**：用户可以用任何方式表达需求
   - "加载数据" ✅
   - "帮我把数据导入一下" ✅
   - "我要开始了，先准备数据" ✅

2. **容错能力**：LLM 可以理解模糊需求
   - "训练一下" → LLM 知道指的是 `train_models`
   - "给 1 号推荐" → LLM 知道是 `recommend(user_id="1")`

3. **上下文理解**：LLM 可以基于对话历史做决策
   - 用户："推荐"
   - LLM："请提供客户ID"
   - 用户："1"
   - LLM：调用 `recommend(user_id="1")`

---

## 六、混合模式的优势

本项目并非纯粹的"提示词控制"或"代码控制"，而是**智能混合**：

### 6.1 提示词控制高层逻辑

```python
MAIN_SYSTEM_PROMPT = """
工作流程建议：用户说「加载数据」时可直接调用 load_data 或 Task(data_agent)；
说「训练模型」时调用 train_models 或 Task(training_agent)...
"""
```
- **优势**：灵活、易于调整、支持自然语言
- **适用场景**：意图理解、流程规划、用户交互

### 6.2 代码控制底层保障

```python
def _ensure_models():
    """若未训练则先加载数据再训练（同步）。"""
    if state["propensity_model"] is not None:
        return state["propensity_model"], state["recommendation_model"]
    # 自动加载数据
    if state["datasets"] is None:
        state["datasets"] = prepare_datasets(size="100k")
    # 执行训练
    ...
```
- **优势**：可靠、可预测、容错性强
- **适用场景**：依赖管理、参数验证、业务实现

### 6.3 分层协作示意图

```
┌─────────────────────────────────────┐
│      用户层（自然语言）               │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│  提示词控制层（LLM 推理）             │
│  - 意图理解                          │
│  - 流程规划                          │
│  - 工具选择                          │
│  - 参数提取                          │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│  代码执行层（工具实现）               │
│  - 参数验证                          │
│  - 业务逻辑                          │
│  - 依赖管理                          │
│  - 状态维护                          │
└─────────────────────────────────────┘
              ↓
┌─────────────────────────────────────┐
│  业务逻辑层（算法实现）               │
│  - 数据加载（data_prep）             │
│  - 模型训练（model_training）        │
└─────────────────────────────────────┘
```

---

## 七、对比其他 Agent 框架

### 7.1 纯代码控制的 Agent（如 LangGraph）

```python
from langgraph.graph import StateGraph

workflow = StateGraph(State)
workflow.add_node("load_data", load_data_node)
workflow.add_node("train_model", train_model_node)
workflow.add_edge("load_data", "train_model")  # 硬编码流程
workflow.set_entry_point("load_data")
```

**特点：**
- ✅ 流程可预测、易于调试
- ❌ 缺乏灵活性，新增流程需修改代码
- ❌ 难以处理自然语言的多样性

### 7.2 纯提示词控制的 Agent（如 ReAct）

```python
prompt = """
You are an AI assistant. You have access to these tools: load_data, train_models.
User: Load data and train model.
Plan your steps and use tools.
"""
```

**特点：**
- ✅ 极度灵活，支持任意自然语言输入
- ❌ 不可靠，可能遗漏步骤或出错
- ❌ 缺乏容错机制

### 7.3 本项目的混合模式

**特点：**
- ✅ **提示词** 提供灵活性和自然交互
- ✅ **代码** 提供可靠性和容错保障
- ✅ **最佳平衡**：既能理解自然语言，又有可靠的执行保障

---

## 八、教学总结：如何判断控制方式？

### 8.1 判断标准

| 问题 | 提示词控制 | 代码控制 |
|------|-----------|---------|
| **谁决定调用哪个工具？** | LLM 通过理解提示词决定 | 代码逻辑（if/switch）决定 |
| **流程是否硬编码？** | 否，LLM 动态规划 | 是，明确的代码分支 |
| **能否处理模糊输入？** | 能，LLM 理解自然语言 | 不能，需精确匹配 |
| **修改流程是否需要改代码？** | 否，修改提示词即可 | 是，需修改代码并部署 |
| **是否依赖 LLM 推理？** | 是 | 否 |

### 8.2 本项目的判断

#### 8.2.1 查看 `agents/definitions.py`

```python
MAIN_SYSTEM_PROMPT = """你是零售贷款智能运营助手...
工作流程建议：用户说「加载数据」时可直接调用 load_data 或 Task(data_agent)...
"""
```
→ **提示词在指导 LLM 如何决策**，这是提示词控制的典型特征

#### 8.2.2 查看 `agents/runner.py`

```python
options = ClaudeAgentOptions(
    system_prompt=MAIN_SYSTEM_PROMPT,  # 注入提示词
    allowed_tools=allowed,             # 工具白名单
    # 没有硬编码的流程图！
)
```
→ **没有 if/else 决定调用哪个工具**，决策权交给 LLM

#### 8.2.3 查看 `tools/loan_agent_tools.py`

```python
async def tool_load_data(args: dict) -> dict:
    """加载示例数据..."""
    datasets = _ensure_datasets()
    return {"content": _text_content(msg)}
```
→ **工具只实现功能，不决定何时被调用**

**结论**：本项目的业务流程控制**主要在提示词层面**，代码仅提供工具能力和可靠性保障。

---

## 九、实战建议

### 9.1 适合用提示词控制的场景

1. **业务流程多变**：需求经常调整，硬编码成本高
2. **自然语言交互**：用户输入不可预测
3. **复杂决策**：需要根据上下文做判断
4. **快速迭代**：修改提示词比修改代码快

### 9.2 适合用代码控制的场景

1. **关键业务逻辑**：不能出错的核心流程
2. **性能敏感**：不希望每次都经过 LLM 推理
3. **确定性流程**：流程固定，无需灵活性
4. **合规要求**：需要可审计的执行路径

### 9.3 混合模式最佳实践

**推荐架构**：
```
提示词控制：用户意图 → 工具选择 → 流程规划
       ↓
代码控制：  参数验证 → 业务实现 → 容错处理
```

**实施要点**：
1. **提示词写清楚**：明确告诉 LLM 工具的用途和使用时机
2. **代码要健壮**：假设 LLM 可能传错参数，做好验证
3. **容错要到位**：代码层自动处理依赖关系（如 `_ensure_datasets()`）
4. **测试要全面**：既测试提示词的理解能力，也测试代码的鲁棒性

---

## 十、总结

### 10.1 核心结论

本项目的 Agent 业务流程控制采用**「提示词主导 + 代码辅助」的混合模式**：

1. **提示词控制**（约 70%）：
   - 用户意图理解
   - 工具选择决策
   - 流程规划
   - 参数提取
   - 结果总结

2. **代码控制**（约 30%）：
   - 工具能力实现
   - 参数验证
   - 依赖管理（如自动加载数据）
   - 状态维护
   - 容错处理

### 10.2 技术洞察

**为什么这种混合模式有效？**

1. **分层解耦**：决策层（LLM）和执行层（代码）各司其职
2. **优势互补**：LLM 的灵活性 + 代码的可靠性
3. **渐进式容错**：提示词建议 → 代码兜底 → 多重保障
4. **易于维护**：业务调整修改提示词，bug 修复改代码

### 10.3 学习要点

对于想要开发类似 Agent 系统的开发者：

1. **不要过度依赖代码控制**：让 LLM 发挥推理能力
2. **不要完全依赖提示词**：关键逻辑要有代码保障
3. **提示词要详细**：给 LLM 提供充分的上下文和指导
4. **代码要健壮**：做好参数验证和异常处理
5. **测试要双管齐下**：既测提示词效果，也测代码逻辑

### 10.4 未来展望

随着 LLM 能力提升，未来可能的演进方向：

1. **更少的代码控制**：LLM 能力增强，可以处理更复杂的决策
2. **更智能的容错**：LLM 自主检测和修复错误
3. **更动态的流程**：根据业务结果实时调整执行计划
4. **更自然的交互**：支持更复杂的多轮对话和上下文理解

但无论如何，**代码层面的可靠性保障将始终是必需的**。

---

## 附录：关键代码文件说明

| 文件 | 作用 | 控制类型 |
|------|------|---------|
| `agents/definitions.py` | 定义主 Agent 和子 Agent 的提示词 | 提示词控制 |
| `agents/runner.py` | 搭建 Agent 运行框架，注入配置 | 代码控制（架构） |
| `tools/loan_agent_tools.py` | 实现 6 个 MCP 工具 | 代码控制（执行） |
| `core/config.py` | 配置模型后端（Ollama/Anthropic） | 代码控制（配置） |
| `app/data_prep.py` | 数据加载业务逻辑 | 代码控制（业务） |
| `app/model_training.py` | 模型训练业务逻辑 | 代码控制（业务） |

**核心理解**：
- `agents/definitions.py` 中的提示词是"大脑"，决定做什么
- `tools/loan_agent_tools.py` 中的工具是"四肢"，执行具体操作
- `agents/runner.py` 是"神经系统"，连接大脑和四肢

---

**报告完成日期**：2026-02-08  
**分析对象**：claude-agent-sdk-demo-retail-loan-ml 项目  
**结论**：业务流程控制以提示词为主，代码为辅，两者协同工作。
