#activar entorno

.venv\Scripts\Activate.ps1 


#Activar dev langgraph

langgraph dev


# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version
# deactivate the virtual environment
deactivate
rm -rf .venv
## init
uv init
uv venv
# add dependencies
uv add --pre langgraph langchain langchain-openai
uv add --pre langchain-anthropic
uv add "fastapi[standard]"
# add dev dependencies
uv add "langgraph-cli[inmem]" --dev
uv add ipykernel --dev
uv add grandalf --dev
# run the agent
uv run langgraph dev
# install the project
uv pip install -e .
[tool.setuptools.packages.find]
where = ["src"]
include = ["*"]


# RUN FASTAPI
uv run fastpai dev ./src/api/main.py