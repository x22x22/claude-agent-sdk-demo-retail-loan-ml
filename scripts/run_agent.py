"""
命令行对话示例：按当前配置的模型后端跑一次 Agent 对话。
从项目根目录运行：python -m scripts.run_agent
"""
import anyio
from agents.runner import run_agent


async def main():
    async for message in run_agent(user_message="加载数据，然后训练模型。"):
        print(message)


if __name__ == "__main__":
    anyio.run(main)
