from typing import Any, Dict

from .base import CodeExecutor

__all__ = ("CodeExecutorFactory",)

class CodeExecutorFactory:
    """用于创建 code executors"""

    @staticmethod
    def create(code_execution_config: Dict[str, Any]) -> CodeExecutor:
        """
        基于 code execution 配置来创建 code Executor

        """
        executor = code_execution_config.get("executor")
        if isinstance(executor, CodeExecutor):
            return executor

        elif executor == "commandline-local":
            from .local_commandline_code_executor import LocalCommandLineCodeExecutor
            return LocalCommandLineCodeExecutor(**code_execution_config.get("commandline-local", {}))
        

