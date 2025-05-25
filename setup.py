#!/usr/bin/env python3
"""
Setup script for Book2Audible
"""
from setuptools import setup, find_packages

setup(
    name="book2audible",
    version="1.0.0",
    author="Book2Audible Team", 
    description="Convert text books to audiobooks using Orpheus TTS",
    url="https://github.com/outtram/Book2Audible",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.9",
    install_requires=[
        "requests>=2.31.0",
        "python-docx>=1.1.0", 
        "pydub>=0.25.1",
        "openai-whisper>=20231117",
        "nltk>=3.8.1",
        "python-dotenv>=1.0.0",
        "click>=8.1.7",
        "tqdm>=4.66.1",
        "colorama>=0.4.6",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "book2audible=book2audible:main",
        ],
    },
    include_package_data=True,
)
