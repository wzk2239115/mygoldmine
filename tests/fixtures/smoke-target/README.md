# smoke-target

T10 容器冒烟用的小仓库。仅用于验证 Docker -> entrypoint -> mine_one -> renderer
链路，不包含真实业务代码。

`app.py` 故意保留一个明显的 `shell=True` 调用，方便冒烟报告引用具体文件与行号。
