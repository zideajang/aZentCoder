import os
from pathlib import Path
import re
import uuid
import warnings
from typing import ClassVar, List, Optional, Union
from pydantic import Field

from ..developerchat.agent import LLMAgent
from ..code_utils import execute_code
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
