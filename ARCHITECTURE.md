# 零售贷款智能运营 — 架构设计图

本文档用 Mermaid 图系统展示整体架构，可在支持 Mermaid 的 Markdown 查看器（如 GitHub、VS Code 插件、Typora）中直接渲染。

---

## 1. 系统总体架构（分层视图）

```mermaid
flowchart TB
    subgraph 用户层
        U[用户]
    end

    subgraph 展示与入口层
        G[Gradio Web UI<br/>Tab1 数据管理 · Tab2 模型训练 · Tab3 模型演示]
        CLI[命令行入口<br/>scripts/run_agent]
    end

    subgraph Agent 层["Agent 层 (claude-agent-sdk)"]
        MAIN[零售贷款运营助手<br/>主 Agent]
        TASK[Task 委派]
        SUB1[data_agent<br/>数据加载与概况]
        SUB2[training_agent<br/>模型训练]
        SUB3[recommendation_agent<br/>推荐与预测]
        MAIN --> TASK
        TASK --> SUB1
        TASK --> SUB2
        TASK --> SUB3
    end

    subgraph MCP 工具层
        MCP[loan_agent MCP Server]
        M1[load_data]
        M2[get_data_summary]
        M3[train_models]
        M4[recommend]
        M5[predict_propensity]
        M6[similar_items]
        MCP --> M1 & M2 & M3 & M4 & M5 & M6
    end

    subgraph 业务与数据层
        APP[app 模块]
        DP[data_prep<br/>数据准备]
        MT[model_training<br/>意愿模型 + 推荐模型]
        STATE[进程内状态<br/>datasets / 已训练模型]
        APP --> DP & MT
        DP --> STATE
        MT --> STATE
    end

    U --> G & CLI
    CLI --> MAIN
    G --> APP
    MAIN <--> MCP
    SUB1 & SUB2 & SUB3 <--> MCP
    MCP --> APP
```

**说明**：用户通过 Gradio 使用数据管理、模型训练、模型演示三个步骤（直接操作 app 与状态）；或通过命令行入口（`scripts/run_agent`）与主 Agent 交互。主 Agent 仅由命令行触发，由 claude-agent-sdk 驱动，模型后端由 `core.config.LLM_BACKEND` 配置。主 Agent 可直接调用 MCP 工具，也可通过 Task 委派子 Agent；子 Agent 与主 Agent 共用同一 MCP 服务，工具实现落在 app 模块并共享进程内状态。

---

## 2. Agent 与 Sub-Agent、MCP 调用关系

```mermaid
flowchart LR
    subgraph 主 Agent
        A[零售贷款运营助手<br/>大模型由 LLM_BACKEND 配置]
    end

    subgraph 工具与委派
        T[Task]
        D[Read / Grep / Glob / Bash]
        M[MCP: loan_agent]
    end

    subgraph 子 Agent
        B1[data_agent]
        B2[training_agent]
        B3[recommendation_agent]
    end

    subgraph MCP 工具
        load[load_data]
        summary[get_data_summary]
        train[train_models]
        rec[recommend]
        pred[predict_propensity]
        sim[similar_items]
    end

    A --> T
    A --> D
    A --> M
    T --> B1 & B2 & B3
    B1 --> load & summary
    B2 --> train
    B3 --> rec & pred & sim
    M --> load & summary & train & rec & pred & sim
```

**说明**：主 Agent 可调用 Task（委派子 Agent）、内置工具（Read/Grep/Glob/Bash）、以及 MCP 的 6 个工具；三个子 Agent 各自只能调用其职责范围内的 MCP 工具。

---

## 3. 命令行 Agent 对话请求流

```mermaid
sequenceDiagram
    participant U as 用户
    participant CLI as 命令行
    participant Runner as Agent Runner
    participant SDK as ClaudeSDKClient
    participant Main as 零售贷款运营助手
    participant Task as Task
    participant Sub as 子 Agent
    participant MCP as loan_agent MCP
    participant App as app 模块

    U->>CLI: 自然语言（如「加载数据，再训练模型」）
    CLI->>Runner: run_agent(msg)（按配置选用后端）
    Runner->>SDK: connect + query(msg)
    SDK->>Main: 推理

    alt 直接调 MCP
        Main->>MCP: load_data / train_models / ...
        MCP->>App: prepare_datasets / train_* / ...
        App-->>MCP: 结果
        MCP-->>Main: 工具结果
    else 委派子 Agent
        Main->>Task: subagent_type, description, prompt
        Task->>Sub: 执行子 Agent
        Sub->>MCP: 调用其可用工具
        MCP->>App: 业务调用
        App-->>MCP: 结果
        MCP-->>Sub: 工具结果
        Sub-->>Task: 子 Agent 回复
        Task-->>Main: 委派结果
    end

    Main-->>SDK: 汇总回复
    SDK-->>Runner: receive_response() 流式
    Runner-->>CLI: yield message
    CLI-->>U: 流式输出
```

**说明**：仅命令行入口（`python -m scripts.run_agent`）触发此流。用户输入经 Runner 进入 SDK（按 `LLM_BACKEND` 选用模型），主 Agent 可选择直接调 MCP 或通过 Task 交给子 Agent；子 Agent 调 MCP → app，结果逐级返回并以流式消息输出到控制台。

---

## 4. 模块与文件映射

```mermaid
flowchart TB
    subgraph 入口与配置
        main[main.py]
        run[scripts/run_agent.py<br/>命令行对话]
        config[core/config.py<br/>LLM_BACKEND / 模型与端口]
    end

    subgraph UI
        ui_app[ui/app.py]
        ui_help[ui/helpers.py]
    end

    subgraph Agent
        def[agents/definitions.py<br/>主 Agent 人设与子 Agent 定义]
        runner[agents/runner.py<br/>按配置选用模型后端]
    end

    subgraph Tools
        loan_tools[tools/loan_agent_tools.py<br/>MCP 工具实现 + set_ui_state]
    end

    subgraph 业务
        data_prep[app/data_prep.py]
        model_train[app/model_training.py]
    end

    subgraph 流式与数据
        consumer[streaming/consumer.py]
        data_dir[data/]
    end

    main --> config & ui_app
    run --> runner
    ui_app --> loan_tools & ui_help
    ui_app --> data_prep & model_train
    runner --> def & loan_tools & config
    loan_tools --> data_prep & model_train
    runner --> consumer
```

**说明**：根目录仅保留 `main.py`；配置在 `core/config.py`，命令行 Agent 对话在 `scripts/run_agent.py`。Web UI（`ui/app.py`）仅含数据管理、模型训练、模型演示三个 Tab，不调用 runner；Agent 仅由 `scripts/run_agent` 调用。数据与模型状态在 `loan_agent_tools` 的进程内状态中，供 UI 与命令行 Agent 共用。

---

## 5. 数据与状态流

```mermaid
flowchart LR
    subgraph 数据来源
        ML[MovieLens 100k]
    end

    subgraph 准备
        PREP[data_prep<br/>prepare_datasets]
    end

    subgraph 状态
        S[(进程内状态<br/>datasets<br/>propensity_model<br/>recommendation_model)]
    end

    subgraph 消费
        UI_T[Tab1~3 界面]
        MCP_T[MCP 工具]
    end

    ML --> PREP
    PREP --> S
    S --> UI_T
    S --> MCP_T
    UI_T -->|加载/训练时| set_ui_state
    set_ui_state --> S
```

**说明**：数据经 data_prep 产出后写入进程内状态；界面操作（加载、训练）通过 `set_ui_state` 同步状态，命令行 Agent 通过 MCP 工具读写同一状态。

---

以上五图从**分层总览、Agent/MCP 关系、对话时序、模块映射、数据状态**五方面描述架构；若需导出为 PNG/SVG，可使用 [Mermaid Live Editor](https://mermaid.live) 或 VS Code 的 Mermaid 插件渲染后导出。
