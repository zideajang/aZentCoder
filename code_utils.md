
关于 `in_docker_container` 函数，如何代码运行在 docker 容器内返回 True，否则返回 False

关于 `is_docker_running` 函数

```python

client = docker.from_env()
client.ping()
```
如果没有抛出 `docker.errors.DockerException`


我们先看测试用例