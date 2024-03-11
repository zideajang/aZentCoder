from __future__ import annotations
import sys

import logging
from pathlib import Path

import atexit
from hashlib import md5
from time import sleep

import uuid
from typing import List, Optional, Type, Union

import docker
from docker.models.containers import Container
from docker.errors import ImageNotFound

from .base import CodeBlock, CodeExecutor, CodeExtractor
from .markdown_code_extractor import MarkdownCodeExtractor
from .local_commandline_code_executor import CommandLineCodeResult
from ..code_utils import TIMEOUT_MSG, _cmd
if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

def _wait_for_ready(container: Container, timeout: int = 60, stop_time: int = 0.1) -> None:
    elapsed_time = 0
    while container.status != "running" and elapsed_time < timeout:
        sleep(stop_time)
        elapsed_time += stop_time
        container.reload()
        continue
    if container.status != "running":
        raise ValueError("Container failed to start")
    

__all__ = ("DockerCommandLineCodeExecutor",)


class DockerCommandLineCodeExecutor(CodeExecutor):
    def __init__(
        self,
        image: str = "python:3-slim",
        container_name: Optional[str] = None,
        timeout: int = 60,
        work_dir: Union[Path, str] = Path("."),
        auto_remove: bool = True,
        stop_container: bool = True,
    ):
        if timeout < 1:
            raise ValueError("Timeout must be greater than or equal to 1.")
        
        if isinstance(work_dir, str):
            work_dir = Path(work_dir)

        if not work_dir.exists():
            raise ValueError(f"Working directory {work_dir} does not exist.")
        
        client = docker.from_env()

        try:
            client.images.get(image)
        except ImageNotFound:
            logging.info(f"Pulling image {image}...")
            # Let the docker exception escape if this fails.
            client.images.pull(image)

        if container_name is None:
            container_name = f"azent-code-exec-{uuid.uuid4()}"

        self._container = client.containers.create(
            image,
            name=container_name,
            entrypoint="/bin/sh",
            tty=True,
            auto_remove=auto_remove,
            volumes={str(work_dir.resolve()): {"bind": "/workspace", "mode": "rw"}},
            working_dir="/workspace",
        )

        self._container.start()

        _wait_for_ready(self._container)

        def cleanup():
            try:
                container = client.containers.get(container_name)
                container.stop()
            except docker.errors.NotFound:
                pass

            atexit.unregister(cleanup)


        if stop_container:
            atexit.register(cleanup)

        self._cleanup = cleanup

        if self._container.status != "running":
            raise ValueError(f"Failed to start container from image {image}. Logs: {self._container.logs()}")

        self._timeout = timeout
        self._work_dir: Path = work_dir


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
    
    def execute_code_blocks(self, code_blocks: List[CodeBlock]) -> CommandLineCodeResult:
        if len(code_blocks) == 0:
            raise ValueError("No code blocks to execute.")
        
        outputs = []
        files = []
        last_exit_code = 0
        for code_block in code_blocks:
            lang = code_block.language
            code = code_block.code
            code_hash = md5(code.encode()).hexdigest()
            # print(code_hash)
            first_line = code.split("\n")[0]
            if first_line.startswith("# filename:"):
                filename = first_line.split(":")[1].strip()
                path = Path(filename)
                if not path.is_absolute():
                    path = Path("/workspace") / path
                path = path.resolve()
                try:
                    path.relative_to(Path("/workspace"))
                except ValueError:
                    return CommandLineCodeResult(exit_code=1, output="Filename is not in the workspace")
            else:
                # create a file with a automatically generated name
                filename = f"tmp_code_{code_hash}.{'py' if lang.startswith('python') else lang}"

            code_path = self._work_dir / filename
            with code_path.open("w", encoding="utf-8") as fout:
                fout.write(code)

            command = ["timeout", str(self._timeout), _cmd(lang), filename]

            result = self._container.exec_run(command)
            exit_code = result.exit_code
            output = result.output.decode("utf-8")
            if exit_code == 124:
                output += "\n"
                output += TIMEOUT_MSG

            outputs.append(output)
            files.append(code_path)

            last_exit_code = exit_code
            if exit_code != 0:
                break

        code_file = str(files[0]) if files else None
        return CommandLineCodeResult(exit_code=last_exit_code, output="".join(outputs), code_file=code_file)


    def restart(self) -> None:
        """(Experimental) Restart the code executor."""
        self._container.restart()
        if self._container.status != "running":
            raise ValueError(f"Failed to restart container. Logs: {self._container.logs()}")

    def stop(self) -> None:
        """(Experimental) Stop the code executor."""
        self._cleanup()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[TracebackType]
    ) -> None:
        self.stop()



if __name__ == "__main__":
    docker_command_code_executor = DockerCommandLineCodeExecutor()