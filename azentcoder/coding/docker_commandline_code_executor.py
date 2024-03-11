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
