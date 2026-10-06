from setuptools import setup, find_packages

setup(
    name="zoro",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "flask>=3.0.0",
        "flask-cors>=4.0.0",
        "pydantic>=2.0.0",
        "python-dotenv>=1.0.0",
        "openai>=1.0.0",
        "tiktoken>=0.5.0",
        # Every CLI command module (backend/cli/commands/*.py, including
        # the external-verifier commands) is click-decorated; this used
        # to ride in only transitively via flask, which is fragile (a
        # flask major version could drop it as a dependency).
        "click>=8.0.0",
        # Additional dependencies for Chinese LLM providers
        "dashscope; platform_system!='Darwin' or python_implementation!='PyPy'",  # For Qwen
        "zhipuai; platform_system!='Darwin' or python_implementation!='PyPy'",   # For Zhipu
    ],
    extras_require={
        "dev": ["pytest>=7.0.0"],
    },
    entry_points={
        'console_scripts': [
            'zoro=backend.cli.cli:cli',
            'zoro-api=backend.api:main',
            'zoro-backend=backend.api:backend_only_main',
        ],
    },
    author="Jenny Ma",
    description="Zoro learning system - process chat logs and search rules",
    python_requires=">=3.10",
)
