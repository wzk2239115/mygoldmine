# curated by env-builder agent (mode=auto, source audit + CPU import/test)
# project=verl commit=174888f source=/home/wzk/mygoldmine/targets/verl
#
# 验收范围：
#   1. 源码烘焙到 /opt/target，editable 安装 verl；
#   2. 无网络、无 GPU 的 CPU 容器内 `import verl` 成功；
#   3. tests/test_protocol_on_cpu.py 与 tests/test_base_config_on_cpu.py 通过。
# 不安装 GPU/vLLM/SGLang/Megatron 等训练后端与完整开发依赖（见 env-manifest.json limitations）。
#
# 依赖源：宿主机已配置 PyPI 清华镜像（~/.config/pip/pip.conf），构建容器不继承该配置，
# 因此在这里显式使用同一通用镜像源；torch 走官方 CPU 索引。
FROM mygoldmine:dev
USER root
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120

COPY --chown=miner:miner . /opt/target
WORKDIR /opt/target

# 1) CPU 版 torch 只从 PyTorch 官方 CPU 索引取；--no-deps 避免拉入 CUDA 组件，
#    其纯 Python 依赖在第 2 层从通用镜像源补齐。
RUN python3 -m pip install --retries 5 --no-deps \
        --index-url https://download.pytorch.org/whl/cpu \
        torch==2.13.0

# 2) verl 顶层导入链（protocol/device/torch_functional）与 CPU 单测所需的最小依赖集合。
#    关键版本显式固定；virtualenv 固定以避免 pip 在 ray[default] 依赖上的长时间回溯。
RUN python3 -m pip install --retries 10 --timeout 120 \
        --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
        --trusted-host pypi.tuna.tsinghua.edu.cn \
        "filelock" "typing-extensions" "setuptools" "sympy" "mpmath" \
        "networkx" "jinja2" "MarkupSafe" "fsspec" \
        "numpy==2.5.4" "packaging==25.0" \
        "tensordict==0.10.0" "ray[default]==2.59.0" "transformers==5.16.1" \
        "pyarrow==26.0.1" "pandas==3.1.0" "TransferQueue==0.1.11" \
        "virtualenv==21.14.5" \
        "pytest==9.2.0" "pytest-asyncio==1.4.1.post1" "pytest-rerunfailures==16.7"

# 3) 补齐项目 requirements.txt 中的其余运行/开发依赖（不含 GPU/vLLM/SGLang 额外包）。
#    torch 已在第 1 层安装并被复用；TransferQueue/tensordict 等版本与第 2 层一致。
RUN python3 -m pip install --retries 10 --timeout 120 \
        --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
        --trusted-host pypi.tuna.tsinghua.edu.cn \
        -r requirements.txt

# 4) editable 安装 verl 本体（依赖已在上一步提供）。
RUN python3 -m pip install --no-deps -e .

RUN chown -R miner:miner /opt/target
USER miner
ENV MYGOLDMINE_PROJECT=verl \
    MYGOLDMINE_COMMIT=174888f \
    MYGOLDMINE_TARGET=/opt/target \
    MYGOLDMINE_MODE=auto
LABEL mygoldmine.project=verl \
      mygoldmine.commit=174888f \
      mygoldmine.mode=auto \
      mygoldmine.source=/home/wzk/mygoldmine/targets/verl
WORKDIR /opt/target
