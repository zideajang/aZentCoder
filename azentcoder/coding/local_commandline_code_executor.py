import os
from pathlib import Path
import re
import uuid
import warnings
from typing import ClassVar, List, Optional, Union
from pydantic import Field

from ..developerchat.agent import LLMAgent
# from ..code_utils import execute_code
from .base import CodeBlock, CodeExecutor, CodeExtractor, CodeResult
from .markdown_code_extractor import MarkdownCodeExtractor

__all__ = (
    "LocalCommandLineCodeExecutor",
    "CommandLineCodeResult",
)


class CommandLineCodeResult(CodeResult):
    """(Experimental) A code result class for command line code executor."""

    code_file: Optional[str] = Field(
        default=None,
        description="The file that the executed code block was saved to.",
    )
class LocalCommandLineCodeExecutor(CodeExecutor):
    DEFAULT_SYSTEM_MESSAGE_UPDATE: ClassVar[
        str
    ] = """
You have been given coding capability to solve tasks using Python code.
In the following cases, suggest python code (in a python coding block) or shell script (in a sh coding block) for the user to execute.
    1. When you need to collect info, use the code to output the info you need, for example, browse or search the web, download/read a file, print the content of a webpage or a file, get the current date/time, check the operating system. After sufficient info is printed and the task is ready to be solved based on your language skill, you can solve the task by yourself.
    2. When you need to perform some task with code, use the code to perform the task and output the result. Finish the task smartly.
Solve the task step by step if you need to. If a plan is not provided, explain your plan first. Be clear which step uses code, and which step uses your language skill.
When using code, you must indicate the script type in the code block. The user cannot provide any other feedback or perform any other action beyond executing the code you suggest. The user can't modify your code. So do not suggest incomplete code which requires users to modify. Don't use a code block if it's not intended to be executed by the user.
If you want the user to save the code in a file before executing it, put # filename: <filename> inside the code block as the first line. Don't include multiple code blocks in one response. Do not ask users to copy and paste the result. Instead, use 'print' function for the output when relevant. Check the execution result returned by the user.
"""
    def __init__(
        self,
        timeout: int = 60,
        work_dir: Union[Path, str] = Path("."),
        system_message_update: str = DEFAULT_SYSTEM_MESSAGE_UPDATE,
    ):
        
        if timeout < 1:
            raise ValueError("Timeout must be greater than or equal to 1.")
        if isinstance(work_dir, str):
            work_dir = Path(work_dir)
        if not work_dir.exists():
            raise ValueError(f"Working directory {work_dir} does not exist.")
        
        self._timeout = timeout
        self._work_dir: Path = work_dir
        self._system_message_update = system_message_update

    class UserCapability:
        def __init__(self, system_message_update: str) -> None:
            self.system_message_update = system_message_update

        def add_to_agent(self, agent: LLMAgent) -> None:
            agent.update_system_message(agent.system_message + self.system_message_update)

    
    @property
    def user_capability(self) -> "LocalCommandLineCodeExecutor.UserCapability":
        return LocalCommandLineCodeExecutor.UserCapability(self._system_message_update)
    

    @property
    def timeout(self) -> int:
        """(Experimental) The timeout for code execution."""
        return self._timeout

    @property
    def work_dir(self) -> Path:
        """(Experimental) The working directory for the code execution."""
        return self._work_dir

    @property
    def code_extractor(self) -> CodeExtractor:
        """(Experimental) Export a code extractor that can be used by an agent."""
        return MarkdownCodeExtractor()
    

    @staticmethod
    def sanitize_command(lang: str, code: str) -> None:
        dangerous_patterns = [
            (r"\brm\s+-rf\b", "Use of 'rm -rf' command is not allowed."),
            (r"\bmv\b.*?\s+/dev/null", "Moving files to /dev/null is not allowed."),
            (r"\bdd\b", "Use of 'dd' command is not allowed."),
            (r">\s*/dev/sd[a-z][1-9]?", "Overwriting disk blocks directly is not allowed."),
            (r":\(\)\{\s*:\|\:&\s*\};:", "Fork bombs are not allowed."),
        ]

        if lang in ["bash", "shell", "sh"]:
            for pattern, message in dangerous_patterns:
                if re.search(pattern, code):
                    raise ValueError(f"Potentially dangerous command detected: {message}")
                

    def execute_code_blocks(self, code_blocks: List[CodeBlock]) -> CommandLineCodeResult:
        logs_all = ""
        for code_block in code_blocks:
            lang, code = code_block.language, code_block.code

            LocalCommandLineCodeExecutor.sanitize_command(lang, code)
            filename_uuid = uuid.uuid4().hex
            filename = None
            if lang in ["bash", "shell", "sh", "pwsh", "powershell", "ps1"]:
                filename = f"{filename_uuid}.{lang}"
                exitcode, logs, _ = execute_code(
                    code=code,
                    lang=lang,
                    timeout=self._timeout,
                    work_dir=str(self._work_dir),
                    filename=filename,
                    use_docker=False,
                )
            elif lang in ["python", "Python"]:
                filename = f"{filename_uuid}.py"
                exitcode, logs, _ = execute_code(
                    code=code,
                    lang="python",
                    timeout=self._timeout,
                    work_dir=str(self._work_dir),
                    filename=filename,
                    use_docker=False,
                )
            else:
                # In case the language is not supported, we return an error message.
                exitcode, logs, _ = (1, f"unknown language {lang}", None)
            logs_all += "\n" + logs
            if exitcode != 0:
                break

        code_filename = str(self._work_dir / filename) if filename is not None else None
        return CommandLineCodeResult(exit_code=exitcode, output=logs_all, code_file=code_filename)