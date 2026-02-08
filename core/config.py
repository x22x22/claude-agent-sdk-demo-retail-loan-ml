"""
配置：模型后端（Ollama / Anthropic 等）、工作目录、allowed_tools 等。
claude-agent-sdk 支持：默认 Anthropic API、Ollama（env 指向本地）、以及 Bedrock/Vertex/Azure 等。
"""
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

# 项目根目录（core 的上一级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 数据与状态目录
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# ---------- 模型后端（二选一或扩展） ----------
# ollama：本地 Ollama，无需 API Key
# anthropic：Anthropic 云端 Claude，需 ANTHROPIC_API_KEY
LLM_BACKEND = os.getenv("LLM_BACKEND", "ollama").strip().lower()

# 本地 Ollama（当 LLM_BACKEND=ollama 时使用）
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:32b")
OLLAMA_ENV = {
    "ANTHROPIC_AUTH_TOKEN": "ollama",
    "ANTHROPIC_API_KEY": "",
    "ANTHROPIC_BASE_URL": OLLAMA_BASE_URL,
}
CLAUDE_CLI = os.getenv("CLAUDE_CLI", "")

# Anthropic 云端（当 LLM_BACKEND=anthropic 时使用，需设置 ANTHROPIC_API_KEY）
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")


def build_ollama_options_kwargs(cwd: str | None = None) -> dict:
    """构建用于 ClaudeAgentOptions 的 kwargs，供本地 Ollama 使用。"""
    kwargs = {
        "model": OLLAMA_MODEL,
        "env": OLLAMA_ENV,
    }
    if CLAUDE_CLI:
        kwargs["cli_path"] = CLAUDE_CLI
    if cwd:
        kwargs["cwd"] = cwd
    return kwargs


def build_anthropic_options_kwargs(cwd: str | None = None) -> dict:
    """构建用于 ClaudeAgentOptions 的 kwargs，供 Anthropic 云端 API 使用。依赖环境变量 ANTHROPIC_API_KEY。"""
    kwargs = {
        "model": ANTHROPIC_MODEL,
    }
    if cwd:
        kwargs["cwd"] = cwd
    return kwargs


def build_agent_options_kwargs(cwd: str | None = None) -> dict:
    """根据 LLM_BACKEND 返回对应后端的 ClaudeAgentOptions kwargs（model、cwd、以及 Ollama 时的 env）。"""
    if LLM_BACKEND == "anthropic":
        return build_anthropic_options_kwargs(cwd=cwd)
    return build_ollama_options_kwargs(cwd=cwd)


# 主 Agent 允许的工具（Read/Grep/Glob/Bash + MCP 自定义工具）
DEFAULT_ALLOWED_TOOLS = ["Read", "Grep", "Glob", "Bash"]

# Web UI：默认监听所有网卡，可通过 http://localhost:7860 访问
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "7860"))
