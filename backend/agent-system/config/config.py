from db.connection import connect_to_db
from memory.memory_manager import MemoryManager
import os
from google import genai
# Table names for each memory type
CONVERSATIONAL_TABLE   = "CONVERSATIONAL_MEMORY" # Episodic memory
KNOWLEDGE_BASE_TABLE   = "SEMANTIC_MEMORY" # Semantic memory
WORKFLOW_TABLE = "WORKFLOW_MEMORY" # Procedural memory
TOOLBOX_TABLE    = "TOOLBOX_MEMORY" # Procedural memory
ENTITY_TABLE = "ENTITY_MEMORY" # Semantic memory
SUMMARY_TABLE = "SUMMARY_MEMORY" # Semantic memory
TOOL_LOG_TABLE = "TOOL_LOG_MEMORY" # Tool execution logs
conn = connect_to_db()
manager = MemoryManager(conn,
                        CONVERSATIONAL_TABLE,
                        KNOWLEDGE_BASE_TABLE,
                        WORKFLOW_TABLE,
                        TOOLBOX_TABLE,
                        ENTITY_TABLE,
                        SUMMARY_TABLE,
                        TOOL_LOG_TABLE
                        )
client = client = genai.Client(api_key=os.getenv('GOOGLE_GEMINI_API_KEY'))