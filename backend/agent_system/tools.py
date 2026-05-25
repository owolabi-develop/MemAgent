from datetime import datetime
from tavily import TavilyClient
import os
from .config import manager,conn
from .toolbox import ToolBox
from .utils import summarise_context_window, summarize_conversation
from .memory_store import StoreManager

tool= ToolBox(manager)


tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

async def search_tavily(query: str, max_results: int = 5):
    """
    Use this function to search the web and store the results in the knowledge base.
    """
    response = tavily_client.search(query=query, max_results=max_results)
    results = response.get("results", [])

    # Write each result to the knowledge base
    for result in results:
        # Create the text content to embed
        text = f"Title: {result.get('title', '')}\nContent: {result.get('content', '')}\nURL: {result.get('url', '')}"
        
        # Create metadata
        metadata = {
            "title": result.get("title", ""),
            "url": result.get("url", ""),
            "score": result.get("score", 0),
            "source_type": "tavily_search",
            "query": query,
            "timestamp": datetime.now().isoformat()
        }
        
        # Write to knowledge base
        await manager.write_knowledge_base(text, metadata)

    return results


async def get_current_time(detailed: bool = False) -> str:
    """
    Returns the current time.
    
    Args:
        detailed: If True, returns detailed format with microseconds
    
    Returns:
        str: Current time as formatted string
    """
    if detailed:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    else:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    

async def read_toolbox(query: str, k: int = 3) -> list[str]:
    """
    Search the toolbox for functions that can help solve a problem or complete a task.
    
    Use this tool when:
    - You encounter an error or unexpected output and need a different approach
    - The currently available tools don't seem sufficient for the task
    - You need to discover what capabilities are available for a specific problem
    - You want to find alternative functions that might handle edge cases better
    
    Args:
        query: A natural language description of what you're trying to accomplish
               or the problem you're trying to solve. Be specific about the task
               or error you're encountering for better results.
        k: Number of relevant tools to return (default: 5)
    
    Returns:
        A list of tool definitions that semantically match your query,
        including their names, descriptions, and parameter schemas.
    
    Example queries:
        - "search for academic papers on machine learning"
        - "fetch and store document content"
        - "get the current date and time"
        - "summarize long text and save to memory"
    """
    return await manager.read_toolbox(query, k=k)



async def expand_summary(summary_id: str) -> str:
    
    """
    Expand a summary reference to retrieve the original conversations.

    Use when you need more details from a [Summary ID: xxx] reference.
    Returns all original messages that were summarized, in chronological order with timestamps.
    """
    # Get the summary text for context
    summary_text = await manager.read_summary_memory(summary_id)

    # Get the original conversations that were summarized
    original_conversations = await manager.read_conversations_by_summary_id(summary_id)

    return f"""
            ## Summary Context
                {summary_text}

                {original_conversations}
            """
            
async def summarize_and_store(text: str, thread_id: str = None) -> str:
    """
    Summarize long text and store in memory.

    If thread_id is provided, summarize unsummarized conversation units from that thread
    and mark exactly those units with the generated summary_id.
    """
    if thread_id:
        result = await summarize_conversation(thread_id)
        if result.get("status") == "nothing_to_summarize":
            return f"No unsummarized messages found for thread {thread_id}."
        return f"Stored as [Summary ID: {result['id']}] {result['description']}"

    result = await summarise_context_window(text, manager)
    if result.get("status") == "nothing_to_summarize":
        return "No content to summarize."
    return f"Stored as [Summary ID: {result['id']}] {result['description']}"
            


async def register_common_tools():
    tables = {"knowledge_base":"SEMANTIC_MEMORY",
              "workflow":"WORKFLOW_MEMORY",
              "toolbox":"TOOLBOX_MEMORY",
              "entity":"ENTITY_MEMORY",
              "summary":"SUMMARY_MEMORY"
              }
    await StoreManager(conn).create_db(tables)
    
    print("registering common tool and keep reference for lookup")
    await tool.register_tool(search_tavily)
    await tool.register_tool(get_current_time)
    await tool.register_tool(summarize_and_store)
    await tool.register_tool(summarize_conversation)
    await tool.register_tool(read_toolbox)
    await tool.register_tool(expand_summary)
    

TOOL_BY_NAME = {"search_tavily":search_tavily,
                "get_current_time":get_current_time,
                "summarize_and_store":summarize_and_store,
                "summarize_conversation":summarize_conversation,
                "read_toolbox":read_toolbox,
                "expand_summary":expand_summary}