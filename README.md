# aZentCoder
开发一个会写代码的 Agent


- ​`r"..."`:  这里 r 是 Python 中的 raw 字符串标记，意味着把反斜杠作为普通字符

- `[ \t]*(\w+)?[ \t]*\r?\n`: 这部分匹配 Markdown 代码块的开始。是代码块的起始标记。`[ \t]*` 匹配任意数量的空格或制表符（如果有的话
- `(\w+)? ` 用于匹配表示语言的文本（比如代码块中的 python）

- `\r?\n` 用于匹配换行束符，这样写的好处是兼容 Unix（\n）和 Windows（\r\n）风格

- `(.*?)`: 这是一个非贪婪匹配，可以匹配任意字符序列，代码块中的实际代码。非贪婪意味着会匹配尽可能短的字符串

- `\r?\n[ \t]*``` `: 用于分匹配代码块的结束


与开始模式相似，但顺序相反，确保匹配 Markdown 代码块的结束。


搭建 Docker 容器的命令环境，也就是通过终端来运行 Docker，然后在容器中执行代码文件，将代码块保存到工作目录下文件后，然后执行容器里面的包含代码块的文件，现在 executor 支持对 python 和 bash、shell 或者 sh 脚本支持。
- container_name 容器的名字
- timeout: 设置超时，默认值为 60
- image 镜像是可选的，默认值为 python:3-slim
- auto_remove 如果为 True docker 停止后自动移除文件
- stop_container 也就是 python 进程退退出后停止容器，默认值为 True


```python
def _wait_for_ready(container: Container, timeout: int = 60, stop_time: int = 0.1) -> None:
    elapsed_time = 0
    while container.status != "running" and elapsed_time < timeout:
        sleep(stop_time)
        elapsed_time += stop_time
        container.reload()
        continue
    if container.status != "running":
        raise ValueError("Container failed to start")
```