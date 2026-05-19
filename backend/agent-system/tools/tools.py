from datetime import datetime
from tavily import TavilyClient
import os
from memory.memory_manager import MemoryManager
from db.connection import connect_to_db

CONVERSATIONAL_TABLE   = "CONVERSATIONAL_MEMORY" # Episodic memory
KNOWLEDGE_BASE_TABLE   = "SEMANTIC_MEMORY" # Semantic memory
WORKFLOW_TABLE = "WORKFLOW_MEMORY" # Procedural memory
TOOLBOX_TABLE    = "TOOLBOX_MEMORY" # Procedural memory
ENTITY_TABLE = "ENTITY_MEMORY" # Semantic memory
SUMMARY_TABLE = "SUMMARY_MEMORY" # Semantic memory
TOOL_LOG_TABLE = "TOOL_LOG_MEMORY" # Tool execution logs

conn = connect_to_db()
memory_manager = MemoryManager(conn,
                        CONVERSATIONAL_TABLE,
                        KNOWLEDGE_BASE_TABLE,
                        WORKFLOW_TABLE,
                        TOOLBOX_TABLE,
                        ENTITY_TABLE,
                        SUMMARY_TABLE,
                        TOOL_LOG_TABLE
                        )


tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

def search_tavily(query: str, max_results: int = 5):
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
        memory_manager.write_knowledge_base(text, metadata)

    return results

def get_current_time(detailed: bool = False) -> str:
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