# 零售贷款智能运营

基于 **claude-agent-sdk** 的零售贷款智能运营系统：支持数据加载与查看、贷款意愿模型与推荐模型训练、个性化推荐与意愿预测；用户可通过界面按钮完成全流程，也可在智能对话中用自然语言下达「加载数据」「训练模型」「给某客户推荐产品」等指令，由 Agent 调用 MCP 工具并流式回复。**模型后端可配置**：支持 SDK 所兼容的本地或云端后端（如 Anthropic 云端 Claude、本地 Ollama 等），通过 `LLM_BACKEND` 与对应环境变量切换。

**整体架构图**（分层、Agent/Sub-Agent/MCP、对话流程、模块与数据流）见 **[ARCHITECTURE.md](ARCHITECTURE.md)**。

**流程控制分析**：想了解本项目中哪些流程是代码控制、哪些是提示词控制？请阅读 **[流程控制分析文档.md](流程控制分析文档.md)**，这是一份教学级别的深度分析文档，详细解析了代码控制与提示词控制的设计原则和最佳实践。

## 功能概览

- **数据管理**：加载示例数据（MovieLens 100k 转贷款场景），查看交互、客户画像、产品画像
- **模型训练**：贷款意愿模型（逻辑回归）+ 推荐模型（SAR），支持训练过程与指标查看
- **模型使用**：个性化推荐、贷款意愿预测、相似产品检索、特征解释
- **智能对话**：自然语言驱动，Agent 通过 MCP 工具完成加载、训练、推荐等操作

## 技术栈

- **claude-agent-sdk**：Agent 编排，模型由配置决定
- **模型后端**：可配置为 **Anthropic 云端 Claude**（需 API Key）或 **本地后端**（如 Ollama，默认 `qwen2.5:32b`），均为 SDK 支持
- **Gradio**：Web UI
- **Pandas / Scikit-learn / Recommenders**：数据处理与机器学习模型

## 基于 claude-agent-sdk 的体现

本工程在以下位置**直接使用** [claude-agent-sdk](https://pypi.org/project/claude-agent-sdk/) 的 API，从而体现「基于 SDK 开发的智能体」：

| 位置 | 使用的 SDK API | 作用 |
|------|----------------|------|
| **`agents/runner.py`** | `from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions` | 用 `ClaudeAgentOptions` 配置模型（由 `config.build_agent_options_kwargs` 按后端提供）、system_prompt、allowed_tools、mcp_servers；用 `ClaudeSDKClient` 的 `connect()` → `query()` → `receive_response()` 驱动对话并流式返回消息。 |
| **`tools/loan_agent_tools.py`** | `from claude_agent_sdk import tool, create_sdk_mcp_server` | 用 `@tool(name, description, schema)` 注册 6 个 MCP 工具（load_data、train_models、recommend 等），用 `create_sdk_mcp_server(name, version, tools=[...])` 创建进程内 MCP 服务，并挂到 `ClaudeAgentOptions.mcp_servers`。 |
| **`core/config.py`** | （为 SDK 提供配置） | `build_agent_options_kwargs(cwd)` 根据 `LLM_BACKEND` 选择后端：云端时返回 `model`（如 `claude-sonnet-4-20250514`）；本地时返回 `model` 与 `env`（如指向 Ollama 的 `ANTHROPIC_BASE_URL`），均符合 SDK 的 `ClaudeAgentOptions` 用法。 |
| **`agents/definitions.py`** | `AgentDefinition`、`MAIN_SYSTEM_PROMPT` | 主 Agent 的 system_prompt；`build_sub_agent_definitions()` 定义三个子 Agent（data_agent、training_agent、recommendation_agent），供主 Agent 通过 **Task** 委派。 |
| **`ui/app.py`（Tab 4 智能对话）** | 调用 `agents.runner.run_agent()` | 用户输入自然语言后，通过 runner 走 SDK 的 `ClaudeSDKClient` 流式输出，并在聊天框展示。 |
| **`scripts/run_agent.py`** | 调用 `run_agent()` | 命令行对话入口（`python -m scripts.run_agent`），按当前配置选用模型后端。 |

**依赖声明**：`requirements.txt` 中显式包含 `claude-agent-sdk>=0.1.0`。

因此，智能体的「理解用户意图 → 决定调用哪个工具或委派子 Agent → 调用 MCP 工具 / Task → 汇总回复」链路由 claude-agent-sdk 完成，本工程提供 MCP 工具、子 Agent 定义与可配置的模型后端（如 Anthropic、Ollama）。

## Sub-Agent（子智能体）架构

主 Agent 除直接调用 MCP 工具外，可通过 **Task** 将任务委派给以下子 Agent，由子 Agent 在独立上下文中执行并返回结果：

| 子 Agent | 职责 | 可用工具 |
|----------|------|----------|
| **data_agent** | 数据加载与概况查询 | load_data、get_data_summary |
| **training_agent** | 模型训练 | train_models |
| **recommendation_agent** | 推荐与意愿预测 | recommend、predict_propensity、similar_items |

- 子 Agent 定义见 `agents/definitions.py` 中的 `build_sub_agent_definitions()`，通过 `ClaudeAgentOptions.agents` 注入。
- 主 Agent 的 `allowed_tools` 包含 **Task**，system_prompt 中约定调用 Task 时传入 `subagent_type`、`description`、`prompt`。
- 用户说「加载数据」「训练模型」「给客户 1 推荐」等时，主 Agent 可选择直接调 MCP 工具，或委派给对应子 Agent 执行。

## 项目结构

```
customer-behavior-ml/
├── app/                    # 业务模块
│   ├── data_prep.py        # 数据准备
│   └── model_training.py   # 意愿模型 + 推荐模型
├── agents/
│   ├── definitions.py      # 主/子 Agent 定义（system_prompt + build_sub_agent_definitions）
│   └── runner.py           # Agent 执行入口（按 LLM_BACKEND 选用模型）
├── core/
│   └── config.py           # 模型后端与端口配置（LLM_BACKEND / Anthropic / Ollama）
├── scripts/
│   └── run_agent.py        # 命令行对话示例
├── tools/
│   └── loan_agent_tools.py # MCP 工具：load_data, train_models, recommend 等
├── streaming/
│   └── consumer.py         # 流式消息格式化
├── ui/
│   └── app.py              # Gradio 界面
├── main.py                 # 启动 Web UI（根目录唯一入口）
├── requirements.txt
└── README.md
```

## 安装与运行

### 1. 环境

- Python 3.10+（claude-agent-sdk 要求）
- **模型后端（任选其一）**：
  - **Anthropic 云端**：在 [Anthropic Console](https://console.anthropic.com) 获取 API Key，设置 `LLM_BACKEND=anthropic` 与 `ANTHROPIC_API_KEY`
  - **本地**：例如 [Ollama](https://ollama.com)，拉取模型后设置 `LLM_BACKEND=ollama`（默认），无需 API Key

### 2. 依赖

```bash
pip install -r requirements.txt
```

### 3. 配置（可选）

复制 `.env.example` 为 `.env`，按需修改：

- **`LLM_BACKEND`**：`anthropic`（云端）或 `ollama`（本地，默认）
- **Anthropic**（`LLM_BACKEND=anthropic`）：必填 **`ANTHROPIC_API_KEY`**，可选 `ANTHROPIC_MODEL`（默认 `claude-sonnet-4-20250514`）
- **本地 Ollama**（`LLM_BACKEND=ollama`）：可选 `OLLAMA_BASE_URL`、`OLLAMA_MODEL`（默认 `qwen2.5:32b`）
- **Web**：`HOST` / `PORT`（默认 `0.0.0.0` / `7860`）

### 4. 启动 Web UI

```bash
python main.py
```

浏览器打开 `http://localhost:7860`即可

### 5. 命令行对话（不启动 UI）

在项目根目录执行：

```bash
python -m scripts.run_agent
```

会向 Agent 发送示例提示「加载数据，然后训练模型。」并打印流式消息（使用当前配置的模型后端）。

## Agent 与 MCP 工具

Agent 的 system_prompt 约定其仅通过以下 MCP 工具与业务交互（见 `agents/definitions.py`、`tools/loan_agent_tools.py`）：

| 工具 | 说明 |
|------|------|
| `load_data` | 加载示例数据（无参数） |
| `get_data_summary` | 查看当前数据概况 |
| `train_models` | 训练意愿模型 + 推荐模型（无参数；缺数据会先加载） |
| `recommend` | 个性化推荐，参数：`user_id`，可选 `top_k` |
| `predict_propensity` | 预测客户对某产品的意愿概率，参数：`user_id`, `item_id` |
| `similar_items` | 相似产品，参数：`item_id`，可选 `top_k` |



## 技术说明

- **Agent 定义**：`agents/definitions.py` 中 `MAIN_SYSTEM_PROMPT` 描述角色与可用 MCP 工具。
- **模型配置**：`core.config.build_agent_options_kwargs(cwd)` 按 `LLM_BACKEND` 提供对应后端的 `ClaudeAgentOptions` 参数（云端多为 `model` + `cwd`，本地可含 `env`）。
- **执行入口**：`agents/runner.run_agent()` 按配置选用模型后端，使用 `ClaudeSDKClient` 的 `connect()` → `query()` → `receive_response()` 流式返回消息。
- **MCP 工具**：通过 `@tool` + `create_sdk_mcp_server` 暴露进程内工具，挂载到 `mcp_servers`；前端 Gradio 聊天框消费流式输出。

## 注意事项

- 首次加载数据会从 recommenders 拉取 MovieLens，可能较慢。
- 模型与数据状态保存在当前进程内存中，重启服务会清空，需重新「加载数据」与「训练模型」。
- 使用本地大模型（如 Ollama `qwen2.5:32b`）时请保证本机资源足够；使用云端时仅需网络与对应 API Key。

## 许可证

MIT License
