from azentcoder.coding.docker_commandline_code_executor import DockerCommandLineCodeExecutor
from azentcoder.coding.base import CodeBlock

# 创建
code_block_1 = CodeBlock(code="print('hello world')",language="python")
code_block_2 = CodeBlock(code="print(1+2)",language="python")

print(__file__)

# 测试 DockerCommandLineCodeExecutor
# code_blocks = [code_block_1,code_block_2]

# docker_commandline_codeexecutor = DockerCommandLineCodeExecutor()
# res = docker_commandline_codeexecutor.execute_code_blocks(code_blocks)
# print(res)