import subprocess
import os
import sys
from .file_search_engine import engine


def browser_search(query: str) -> bool:
    """
    Launches user's preferred web browser and opens search results for the given query.
    Used when the user asks to find information online.

    Args:
        query: The search query.

    Returns:
        Result true if succeeded, false if failed.
    """
    try:
        name = f"firefox \"https://www.google.lv/search?q={query}\""
        if sys.platform == "win32":
            # most commands on Windows need "start" for OS to find them automatically
            # empty quotes are important for opening objects with default apps
            name = f"start \"\" \"{name}\""

        print(f"Launching {name}...")
        subprocess.Popen(name, shell=True)
        return True
    except Exception as e:
        print(f"Failed to start command '{name}': {e}")
        
    return False 


def find_file_path_by_parts(query: str) -> str:
    """
    Finds file paths on the user's computer based on a partial name match.
    Useful when the user asks "Find me the image I have somewhere on my computer, it could be named something like `dog`".
    Can be called multiple times with different queries to pick the best candidate.
    
    Args:
        query: Parts of possible file name to look for. Include extensions for file types, e.g. doc or txt for documents, jpg for imapes, mp4 for videos etc.
    
    Returns:
        The best matching path for the query or empty string if no good match found.
    """
    print(f"Searching for: '{query}'")
    match = engine.search(query)

    print(match)
    if match is None:
        return ""
    (path, _) = match

    return path


def open_directory(path: str) -> bool:
    """
    Opens the directory for the given file. Useful after finding files by user's request, to guide the user to the location of the file.
    
    Args:
        path: The path to the directory.
    
    Returns:
        Result true if succeeded, false if failed.
    """
    print(f"Opening directory for: '{path}'")
    try:
        
        folder = os.path.dirname(path)
        name = folder
        if sys.platform == "win32":   
            # most commands on Windows need "start" for OS to find them automatically
            # empty quotes are important for opening objects with default apps
            name = f"start \"\" \"{name}\""

        print(f"Launching {name}...")
        subprocess.Popen(name, shell=True)
        return True
    except Exception as e:
        print(f"Failed to start command '{name}': {e}")


def open_file(path: str) -> bool:
    """
    Opens the given file using default viewer application. Useful after finding files by user's request.
    
    Args:
        path: The path to the file.
    
    Returns:
        Result true if succeeded, false if failed.
    """
    print(f"Opening file: '{path}'")
    try:
        name = path
        if sys.platform == "win32":   
            # most commands on Windows need "start" for OS to find them automatically
            # empty quotes are important for opening objects with default apps
            name = f"start \"\" \"{name}\""

        print(f"Launching {name}...")
        subprocess.Popen(name, shell=True)
        return True
    except Exception as e:
        print(f"Failed to start command '{name}': {e}")



TOOL_RESULT = "[TOOL SYSTEM RESPONSE: {result}]"
def format_tool_result(result):
    return TOOL_RESULT.format(result=str(result))


###############################
# Manual tool processing
# https://www.decodingai.com/p/tool-calling-from-scratch-to-production
# This was simplified by using Google's own SDK built-in formatting,
# but left here just for learning purposes or other models.
import json

BROWSER_SEARCH_SCHEMA = {
    "name": "google_search",
    "description": "Tool to launch user's preferred browser and open search results for the given query. Returns True if succeeded, False if something went wrong.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query.",
            }
        },
        "required": ["query"],
    }
}

TOOLS = {
    "google_search": {
        "handler": browser_search,
        "declaration": BROWSER_SEARCH_SCHEMA,
    },
}

TOOLS_BY_NAME = {tool_name: tool["handler"] for tool_name, tool in TOOLS.items()}
TOOLS_SCHEMA = [tool["declaration"] for tool in TOOLS.values()]


def format_system_prompt_for_tools(sysprompt):
    return sysprompt.format(tools=str(TOOLS_SCHEMA))


def extract_tool_call(response_text: str) -> str:
    return response_text.split("<tool_call>")[1].split("</tool_call>")[0].strip()


def has_tool_call(text) -> bool:
    return text.find("<tool_call>") != -1


def call_tool(text: str) -> object:
    if not has_tool_call(text):
        return False
    
    try:
        tool_call_str = extract_tool_call(text)
        tool_call = json.loads(tool_call_str)

        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_handler = TOOLS_BY_NAME[tool_name]

        res = tool_handler(**tool_args)
        return res
    except Exception as e:
        print(f"Error from tool `{text}` call: {e}")
    
    return False

#######################
# simplified for Gemini

TOOL_NAMES = {"browser_search": browser_search }

def call_tool(function_call) -> any:
    tool_name = function_call.name
    tool_args = {key: value for key, value in function_call.args.items()}

    tool_handler = TOOL_NAMES[tool_name]

    return tool_handler(**tool_args)

# tool_result = call_tool(function_call)