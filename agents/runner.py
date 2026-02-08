"""
使用 claude-agent-sdk 驱动零售贷款智能运营，支持 Ollama（本地）或 Anthropic 云端等后端。
自定义 MCP 工具需通过 ClaudeSDKClient 使用，故采用 connect + query + receive_response 流式 yield。
"""
from typing import AsyncIterator, Any

from core.config import build_agent_options_kwargs, PROJECT_ROOT
from agents.definitions import MAIN_SYSTEM_PROMPT, build_sub_agent_definitions
from tools.loan_agent_tools import build_loan_agent_mcp_server, get_loan_agent_allowed_tools


async def run_agent(user_message: str) -> AsyncIterator[Any]:
    """
    根据 core.config.LLM_BACKEND 使用对应后端（ollama / anthropic 等）执行对话，流式 yield 消息。
    工作目录为项目根，Agent 通过 MCP 工具完成加载数据、训练、推荐等。
    """
    try:
        from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
    except ImportError as e:
        yield {"type": "error", "message": f"未安装 claude-agent-sdk: {e}"}
        return

    cwd = str(PROJECT_ROOT)
    agent_kw = build_agent_options_kwargs(cwd=cwd)
    allowed = ["Read", "Grep", "Glob", "Bash", "Task"] + get_loan_agent_allowed_tools()
    mcp_server = build_loan_agent_mcp_server()
    sub_agents = build_sub_agent_definitions()
    options_dict = {
        **agent_kw,
        "system_prompt": MAIN_SYSTEM_PROMPT,
        "allowed_tools": allowed,
        "disallowed_tools": ["Write", "Edit"],
    }
    if mcp_server is not None:
        options_dict["mcp_servers"] = {"loan_agent": mcp_server}
    if sub_agents:
        options_dict["agents"] = sub_agents
    options = ClaudeAgentOptions(**options_dict)

    async with ClaudeSDKClient(options=options) as client:
        await client.connect()
        await client.query(user_message, session_id="default")
        async for message in client.receive_response():
            yield message
