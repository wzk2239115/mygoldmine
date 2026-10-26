"""T10 冒烟目标：故意保留一个命令拼接问题用于报告引用。"""

import subprocess


def convert(filename):
    command = "convert " + filename + " /tmp/out.png"
    return subprocess.run(command, shell=True, check=False)
