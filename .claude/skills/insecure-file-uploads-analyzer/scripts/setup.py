from setuptools import setup, find_packages

setup(
    name="insecure-upload-sink-detector",
    version="1.0.0",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=["tree-sitter>=0.20.0", "pyyaml>=6.0"],
)
