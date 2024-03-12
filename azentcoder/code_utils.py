import logging
import os
import pathlib
import re
import string
import subprocess
import sys
import time

from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import docker

from azentcoder import oai

SENTINEL = object()
DEFAULT_MODEL = "gpt-4"
FAST_MODEL = "gpt-3.5-turbo"

CODE_BLOCK_PATTERN = r"```[ \t]*(\w+)?[ \t]*\r?\n(.*?)\r?\n[ \t]*```"
WORKING_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "extensions")
UNKNOWN = "unknown"
TIMEOUT_MSG = "Timeout"
DEFAULT_TIMEOUT = 600
WIN32 = sys.platform == "win32"
PATH_SEPARATOR = WIN32 and "\\" or "/"
import logging
logger = logging.getLogger(__name__)


# import rich
UNKNOWN = "unknown"

def content_str(content: Union[str, List[Dict[str, Any]], None]) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        raise TypeError(f"content must be None, str, or list, but got {type(content)}")

    rst = ""
    for item in content:
        if not isinstance(item, dict):
            raise TypeError("Wrong content format: every element should be dict if the content is a list.")
        assert "type" in item, "Wrong content format. Missing 'type' key in content's dict."
        if item["type"] == "text":
            rst += item["text"]
        elif item["type"] == "image_url":
            rst += "<image>"
        else:
            raise ValueError(f"Wrong content format: unknown type {item['type']} within the content")
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

def extract_code(
    text: Union[str, List], pattern: str = CODE_BLOCK_PATTERN, detect_single_line_code: bool = False
) -> List[Tuple[str, str]]:
    text = content_str(text)
    if not detect_single_line_code:
        match = re.findall(pattern, text, flags=re.DOTALL)
        return match if match else [(UNKNOWN, text)]
    code_pattern = re.compile(CODE_BLOCK_PATTERN + r"|`([^`]+)`")
    code_blocks = code_pattern.findall(text)
    extracted = []
    for lang, group1, group2 in code_blocks:
        if group1:
            extracted.append((lang.strip(), group1.strip()))
        elif group2:
            extracted.append(("", group2.strip()))

    return extracted



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

def generate_code(pattern: str = CODE_BLOCK_PATTERN, **config) -> Tuple[str, float]:
    pass

_IMPROVE_FUNCTION_CONFIG = {
    "prompt": """Improve the function '{func_name}' to achieve the objective '{objective}'.
The current implementation of the function is as follows:
{file_string}""",
    "model": DEFAULT_MODEL,
    "request_timeout": 600,
}

powershell_command = get_powershell_command()

def _cmd(lang):
    if lang.startswith("python") or lang in ["bash", "sh", powershell_command]:
        return lang
    if lang in ["shell"]:
        return "sh"
    if lang in ["ps1", "pwsh", "powershell"]:
        return powershell_command

    raise NotImplementedError(f"{lang} not recognized in code execution")

def improve_function(file_name, func_name, objective, **config):
    """(openai<1) Improve the function to achieve the objective."""
    params = {**_IMPROVE_FUNCTION_CONFIG, **config}
    # read the entire file into a str
    with open(file_name, "r") as f:
        file_string = f.read()

    return ""
    # response = oai.Completion.create(
    #     {"func_name": func_name, "objective": objective, "file_string": file_string}, **params
    # )
    # return oai.Completion.extract_text(response)[0], response["cost"]

_IMPROVE_CODE_CONFIG = {
    "prompt": """Analyze the code in the following files and return a list of suggestions for improvement{followup}, to achieve the objective of '{objective}'.
{code}
""",
    "model": DEFAULT_MODEL,
    "request_timeout": 900,
}

def _sanitize_filename_for_docker_tag(filename: str) -> str:
    """Convert a filename to a valid docker tag.
    See https://docs.docker.com/engine/reference/commandline/tag/ for valid tag
    format.

    Args:
        filename (str): The filename to be converted.

    Returns:
        str: The sanitized Docker tag.
    """
    # Replace any character not allowed with an underscore
    allowed_chars = set(string.ascii_letters + string.digits + "_.-")
    sanitized = "".join(char if char in allowed_chars else "_" for char in filename)

    # Ensure it does not start with a period or a dash
    if sanitized.startswith(".") or sanitized.startswith("-"):
        sanitized = "_" + sanitized[1:]

    # Truncate if longer than 128 characters
    return sanitized[:128]


def is_docker_running() -> bool:
    """Check if docker is running.

    Returns:
        bool: True if docker is running; False otherwise.
    """
    try:
        client = docker.from_env()
        client.ping()
        return True
    except docker.errors.DockerException:
        return False

def in_docker_container() -> bool:
    """检查代码是否运行在 docker 容器

    Returns:
        bool: True if the code is running in a docker container; False otherwise.
    """
    return os.path.exists("/.dockerenv")

def decide_use_docker(use_docker) -> bool:
    if use_docker is None:
        env_var_use_docker = os.environ.get("AUTOGEN_USE_DOCKER", "True")

        truthy_values = {"1", "true", "yes", "t"}
        falsy_values = {"0", "false", "no", "f"}

        # Convert the value to lowercase for case-insensitive comparison
        env_var_use_docker_lower = env_var_use_docker.lower()

        # Determine the boolean value based on the environment variable
        if env_var_use_docker_lower in truthy_values:
            use_docker = True
        elif env_var_use_docker_lower in falsy_values:
            use_docker = False
        elif env_var_use_docker_lower == "none":  # Special case for 'None' as a string
            use_docker = None
        else:
            # Raise an error for any unrecognized value
            raise ValueError(
                f'Invalid value for AUTOGEN_USE_DOCKER: {env_var_use_docker}. Please set AUTOGEN_USE_DOCKER to "1/True/yes", "0/False/no", or "None".'
            )
    return use_docker

def check_can_use_docker_or_throw(use_docker) -> None:
    if use_docker is not None:
        inside_docker = in_docker_container()
        docker_installed_and_running = is_docker_running()
        if use_docker and not inside_docker and not docker_installed_and_running:
            raise RuntimeError(
                "Code execution is set to be run in docker (default behaviour) but docker is not running.\n"
                "The options available are:\n"
                "- Make sure docker is running (advised approach for code execution)\n"
                '- Set "use_docker": False in code_execution_config\n'
                '- Set AUTOGEN_USE_DOCKER to "0/False/no" in your environment variables'
            )

# 执行代码
def execute_code(
    code: Optional[str] = None,
    timeout: Optional[int] = None,
    filename: Optional[str] = None,
    work_dir: Optional[str] = None,
    use_docker: Union[List[str], str, bool] = SENTINEL,
    lang: Optional[str] = "python",
) -> Tuple[int, str, Optional[str]]:
    if all((code is None, filename is None)):
        error_msg = f"Either {code=} or {filename=} must be provided."
        logger.error(error_msg)
        raise AssertionError(error_msg)

    running_inside_docker = in_docker_container()
    docker_running = is_docker_running()

    # SENTINEL is used to indicate that the user did not explicitly set the argument
    if use_docker is SENTINEL:
        use_docker = decide_use_docker(use_docker=None)
    check_can_use_docker_or_throw(use_docker)

    timeout = timeout or DEFAULT_TIMEOUT
    original_filename = filename
    if WIN32 and lang in ["sh", "shell"] and (not use_docker):
        lang = "ps1"
    if filename is None:
        code_hash = md5(code.encode()).hexdigest()
        # create a file with a automatically generated name
        filename = f"tmp_code_{code_hash}.{'py' if lang.startswith('python') else lang}"
    if work_dir is None:
        work_dir = WORKING_DIR

    filepath = os.path.join(work_dir, filename)
    file_dir = os.path.dirname(filepath)
    os.makedirs(file_dir, exist_ok=True)

    if code is not None:
        with open(filepath, "w", encoding="utf-8") as fout:
            fout.write(code)

    if not use_docker or running_inside_docker:
        # already running in a docker container
        cmd = [
            sys.executable if lang.startswith("python") else _cmd(lang),
            f".\\{filename}" if WIN32 else filename,
        ]
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                subprocess.run,
                cmd,
                cwd=work_dir,
                capture_output=True,
                text=True,
            )
            try:
                result = future.result(timeout=timeout)
            except TimeoutError:
                if original_filename is None:
                    os.remove(filepath)
                return 1, TIMEOUT_MSG, None
        if original_filename is None:
            os.remove(filepath)
        if result.returncode:
            logs = result.stderr
            if original_filename is None:
                abs_path = str(pathlib.Path(filepath).absolute())
                logs = logs.replace(str(abs_path), "").replace(filename, "")
            else:
                abs_path = str(pathlib.Path(work_dir).absolute()) + PATH_SEPARATOR
                logs = logs.replace(str(abs_path), "")
        else:
            logs = result.stdout
        return result.returncode, logs, None

    # create a docker client
    if use_docker and not docker_running:
        raise RuntimeError(
            "Docker package is missing or docker is not running. Please make sure docker is running or set use_docker=False."
        )

    client = docker.from_env()

    image_list = (
        ["python:3-slim", "python:3", "python:3-windowsservercore"]
        if use_docker is True
        else [use_docker]
        if isinstance(use_docker, str)
        else use_docker
    )
    for image in image_list:
        # check if the image exists
        try:
            client.images.get(image)
            break
        except docker.errors.ImageNotFound:
            # pull the image
            print("Pulling image", image)
            try:
                client.images.pull(image)
                break
            except docker.errors.DockerException:
                print("Failed to pull image", image)
    # get a randomized str based on current time to wrap the exit code
    exit_code_str = f"exitcode{time.time()}"
    abs_path = pathlib.Path(work_dir).absolute()
    cmd = [
        "sh",
        "-c",
        f'{_cmd(lang)} "{filename}"; exit_code=$?; echo -n {exit_code_str}; echo -n $exit_code; echo {exit_code_str}',
    ]
    # create a docker container
    container = client.containers.run(
        image,
        command=cmd,
        working_dir="/workspace",
        detach=True,
        # get absolute path to the working directory
        volumes={abs_path: {"bind": "/workspace", "mode": "rw"}},
    )
    start_time = time.time()
    while container.status != "exited" and time.time() - start_time < timeout:
        # Reload the container object
        container.reload()
    if container.status != "exited":
        container.stop()
        container.remove()
        if original_filename is None:
            os.remove(filepath)
        return 1, TIMEOUT_MSG, image
    # get the container logs
    logs = container.logs().decode("utf-8").rstrip()
    # commit the image
    tag = _sanitize_filename_for_docker_tag(filename)
    container.commit(repository="python", tag=tag)
    # remove the container
    container.remove()
    # check if the code executed successfully
    exit_code = container.attrs["State"]["ExitCode"]
    if exit_code == 0:
        # extract the exit code from the logs
        pattern = re.compile(f"{exit_code_str}(\\d+){exit_code_str}")
        match = pattern.search(logs)
        exit_code = 1 if match is None else int(match.group(1))
        # remove the exit code from the logs
        logs = logs if match is None else pattern.sub("", logs)

    if original_filename is None:
        os.remove(filepath)
    if exit_code:
        logs = logs.replace(f"/workspace/{filename if original_filename is None else ''}", "")
    # return the exit code, logs and image
    return exit_code, logs, f"python:{tag}"


_GENERATE_ASSERTIONS_CONFIG = {
    "prompt": """Given the signature and docstring, write the exactly same number of assertion(s) for the provided example(s) in the docstring, without assertion messages.

func signature:
{definition}
assertions:""",
    "model": FAST_MODEL,
    "max_tokens": 256,
    "stop": "\n\n",
}



def generate_assertions(definition: str, **config) -> Tuple[str, float]:
    """(openai<1) Generate assertions for a function.

    Args:
        definition (str): The function definition, including the signature and docstr.
        config (Optional, dict): The configuration for the API call.

    Returns:
        str: The generated assertions.
        float: The cost of the generation.
    """
    params = {**_GENERATE_ASSERTIONS_CONFIG, **config}
    response = oai.Completion.create(
        {"definition": definition},
        **params,
    )
    # assertions = oai.Completion.extract_text(response)[0]
    return assertions, response["cost"]

def implement(
    definition: str,
    configs: Optional[List[Dict]] = None,
    assertions: Optional[Union[str, Callable[[str], Tuple[str, float]]]] = generate_assertions,
) -> Tuple[str, float]:
    """(openai<1) Implement a function from a definition.

    Args:
        definition (str): The function definition, including the signature and docstr.
        configs (list): The list of configurations for completion.
        assertions (Optional, str or Callable): The assertion code which serves as a filter of the responses, or an assertion generator.

    Returns:
        str: The implementation.
        float: The cost of the implementation.
        int: The index of the configuration which generates the implementation.
    """
    cost = 0
    configs = configs or _IMPLEMENT_CONFIGS
    if len(configs) > 1 and callable(assertions):
        assertions, cost = assertions(definition)
    assertion_filter = PassAssertionFilter(assertions)
    response = oai.Completion.create(
        {"definition": definition}, config_list=configs, filter_func=assertion_filter.pass_assertions
    )
    cost += assertion_filter.cost + response["cost"]
    return assertion_filter.responses[assertion_filter.metrics["index_selected"]], cost, response["config_id"]
