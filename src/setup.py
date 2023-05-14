from codecs import open
from os import path

from setuptools import setup

HERE = path.abspath(path.dirname(__file__))

with open(path.join(HERE, "README.md"), encoding="utf-8") as f:
    long_description = f.read()


setup(
    name="smart-home",
    version="0.1.0",
    description="Smart Home Scenarios",
    long_description=long_description,
    long_description_content_type="text/markdown",
    # url="https://home.readthedocs.io/",
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
    packages=["home"],
    include_package_data=True,
    install_requires=[
        "aiohttp[speedups]",
        "aiofiles",
        "pyyaml",
        "python-telegram-bot[all,ext]",
        "telegram",
        "pydantic[dotenv]",
        "async_lru",
        "astral",
    ],
    setup_requires=["pytest-runner"],
    tests_require=[
        "pytest",
        "pytest-mock",
        "pytest-asyncio",
        "pytest-aiohttp",
        "python-dotenv",
    ],
    test_suite="tests",
)
