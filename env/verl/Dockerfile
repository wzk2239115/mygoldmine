# project=verl commit=174888f source=/home/wzk/mygoldmine/targets/verl
# 审计用最小 CPU 沙箱：源码可读、Python 可运行、隔离边界成立。
# 刻意不安装 torch / Ray / transformers / GPU 训练栈，也不安装运行时依赖；
# 仅在 base 镜像上放入源码并做 editable(--no-deps) 注册包元数据。
FROM mygoldmine:dev
USER root
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120

# 源码即上下文；不在构建期下载运行时依赖。
COPY --chown=miner:miner . /opt/target
WORKDIR /opt/target
# 仅注册包元数据，不解析/安装依赖（--no-deps）。
RUN python3 -m pip install --no-cache-dir -e . --no-deps
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
