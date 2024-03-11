import os

import setuptools

here = os.path.abspath(os.path.dirname(__file__))

with open("README.md", "r", encoding="UTF-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="azentcoder",
    version="1.0.0",
    author="zidea",
    author_email="email",
    description="azent frameworker coder",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/zideajang/aZentCoder",
    packages=setuptools.find_packages(include=["azentcoder"],exclude=["test"]),
    python_requires=">=3.8,<3.13",
)