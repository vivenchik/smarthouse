from codecs import open
from os import path

from setuptools import setup

HERE = path.abspath(path.dirname(__file__))

with open(path.join(HERE, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

extras = {
    "dev": [
        "black",
        "isort",
        "mypy",
        "types-PyYAML",
        "types-aiofiles",
        "flake8",
        "flake8-pyproject",
        "pytest",
        "pytest-mock",
        "pytest-asyncio",
        "pytest-aiohttp",
        "pytest-xdist",
        "pytest-cov",
        "no_implicit_optional",
        "python-dotenv",
    ]
}


setup(
    name="smarthouse",
    version="2.0.0",
    description="Smart House Scenarios",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://smarthouselib.readthedocs.io/",
    author="Ivan Kriuchkov",
    author_email="vivenchik@gmail.com",
    license="MIT",
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    packages=["smarthouse"],
    include_package_data=True,
    install_requires=[
        "aiohttp[speedups]",
        "aiofiles",
        "pyyaml",
        "python-telegram-bot[all,ext]",
        "telegram",
        "pydantic[dotenv]<2",
        "async_lru",
        "astral",
        "homeassistant_api>=4",
    ],
    extras_require=extras,
    setup_requires=["pytest-runner"],
    tests_require=[
        "pytest",
        "pytest-mock",
        "pytest-asyncio",
        "pytest-aiohttp",
        "python-dotenv",
        "pytest-runner",
    ],
    test_suite="tests",
)
