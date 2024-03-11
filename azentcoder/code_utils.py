import logging
import os
import pathlib
import re
import string
import subprocess
import sys
import time

from pydantic import BaseModel

from typing import Callable, Dict, List, Optional, Tuple, Union

try:
    import docker
except ImportError:
    docker = None

CODE_BLOCK_PATTERN = r"```[ \t]*(\w+)?[ \t]*\r?\n(.*?)\r?\n[ \t]*```"
WORKING_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "extensions")
UNKNOWN = "unknown"
TIMEOUT_MSG = "Timeout"
DEFAULT_TIMEOUT = 600
WIN32 = sys.platform == "win32"
PATH_SEPARATOR = WIN32 and "\\" or "/"
import logging

# import rich
UNKNOWN = "unknown"

class CodeContent(BaseModel):
    pass
    

def content_str(content: Union[str, List]) -> str:
    if type(content) is str:
        return content
    rst = ""
    for item in content:
        if item["type"] == "text":
            rst += item["text"]
        else:
            assert isinstance(item, dict) and item["type"] == "image_url", "Wrong content format."
            rst += "<image>"
    return rst


def infer_lang(code):
    """infer the language for the code.
    TODO: make it robust.
    """
    if code.startswith("python ") or code.startswith("pip") or code.startswith("python3 "):
        return "sh"

    # check if code is a valid python code
    try:
        compile(code, "test", "exec")
        return "python"
    except SyntaxError:
        # not a valid python code
        return UNKNOWN

def get_powershell_command():
    try:
        result = subprocess.run(["powershell", "$PSVersionTable.PSVersion.Major"], capture_output=True, text=True)
        if result.returncode == 0:
            return "powershell"

    except FileNotFoundError:
        # This means that 'powershell' command is not found so now we try looking for 'pwsh'
        try:
            result = subprocess.run(
                ["pwsh", "-Command", "$PSVersionTable.PSVersion.Major"], capture_output=True, text=True
            )
            if result.returncode == 0:
                return "pwsh"

        except FileNotFoundError:
            if WIN32:
                logging.warning("Neither powershell nor pwsh is installed but it is a Windows OS")
            return None


powershell_command = get_powershell_command()

def _cmd(lang):
    if lang.startswith("python") or lang in ["bash", "sh", powershell_command]:
        return lang
    if lang in ["shell"]:
        return "sh"
    if lang in ["ps1", "pwsh", "powershell"]:
        return powershell_command

    raise NotImplementedError(f"{lang} not recognized in code execution")

def generate_code(pattern: str = CODE_BLOCK_PATTERN, **config) -> Tuple[str, float]:
    """(openai<1) Generate code.

    Args:
        pattern (Optional, str): The regular expression pattern for finding the code block.
            The default pattern is for finding a code block in a markdown file.
        config (Optional, dict): The configuration for the API call.

    Returns:
        str: The generated code.
        float: The cost of the generation.
    """
    # response = oai.Completion.create(**config)
    response = None
    return extract_code(oai.Completion.extract_text(response)[0], pattern), response["cost"]