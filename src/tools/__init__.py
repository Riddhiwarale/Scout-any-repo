from .grep_tool import make_grep_tool
from .glob_tool import make_glob_tool
from .read_tool import make_read_tool
from .bash_tool import make_bash_tool
from .symbol_extractor import make_symbol_extractor_tool


def create_tools(repo_path: str) -> list:
    """
    Factory that returns all tool instances bound to the given repo_path.
    Each tool is a LangChain @tool that can be passed to a ChatAnthropic
    .bind_tools() call or a LangGraph ToolNode.
    """
    return [
        make_grep_tool(repo_path),
        make_glob_tool(repo_path),
        make_read_tool(repo_path),
        make_bash_tool(repo_path),
        make_symbol_extractor_tool(repo_path),
    ]
