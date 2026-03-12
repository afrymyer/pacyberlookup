"""Setup script for PA Cyber Incident Detection Feed."""

from setuptools import find_packages, setup

setup(
    name="pacyberlookup",
    version="0.1.0",
    description="PA Cyber Incident Detection Feed - monitors for cyber incidents affecting Pennsylvania organizations",
    packages=find_packages(),
    python_requires=">=3.11",
    entry_points={
        "console_scripts": [
            "pacyberlookup=pacyberlookup.__main__:main",
        ],
    },
)
