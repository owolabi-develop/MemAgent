from db.connection import connect_to_db,create_vector_index
from memory.memory_store import StoreManager
from memory.memory_manager import MemoryManager
import inspect
from tools.tools import search_tavily
from tools.toolbox import ToolBox
from pprint import pprint
from datetime import datetime


# Table names for each memory type
CONVERSATIONAL_TABLE   = "CONVERSATIONAL_MEMORY" # Episodic memory
KNOWLEDGE_BASE_TABLE   = "SEMANTIC_MEMORY" # Semantic memory
WORKFLOW_TABLE = "WORKFLOW_MEMORY" # Procedural memory
TOOLBOX_TABLE    = "TOOLBOX_MEMORY" # Procedural memory
ENTITY_TABLE = "ENTITY_MEMORY" # Semantic memory
SUMMARY_TABLE = "SUMMARY_MEMORY" # Semantic memory
TOOL_LOG_TABLE = "TOOL_LOG_MEMORY" # Tool execution logs


conn = connect_to_db()

# StoreManager(conn, table_names={
#         'knowledge_base': KNOWLEDGE_BASE_TABLE,
#         'workflow': WORKFLOW_TABLE,
#         'toolbox': TOOLBOX_TABLE,
#         'entity': ENTITY_TABLE,
#         'summary': SUMMARY_TABLE,
#     },)

# create_vector_index(KNOWLEDGE_BASE_TABLE,conn)
# create_vector_index(WORKFLOW_TABLE,conn)
# create_vector_index(TOOLBOX_TABLE,conn)
# create_vector_index(ENTITY_TABLE,conn)
# create_vector_index(SUMMARY_TABLE,conn)

manager = MemoryManager(conn,
                        CONVERSATIONAL_TABLE,
                        KNOWLEDGE_BASE_TABLE,
                        WORKFLOW_TABLE,
                        TOOLBOX_TABLE,
                        ENTITY_TABLE,
                        SUMMARY_TABLE,
                        TOOL_LOG_TABLE
                        )

sample_data = [
  {
    "text": "FastAPI is a high-performance Python framework used to build RESTful APIs with automatic OpenAPI documentation and async support.",
    "metadata": {
      "category": "backend",
      "topic": "fastapi",
      "difficulty": "beginner"
    }
  },
  {
    "text": "Redis is an in-memory datastore commonly used for caching, distributed locks, and session management in scalable systems.",
    "metadata": {
      "category": "database",
      "topic": "redis",
      "difficulty": "intermediate"
    }
  },
  {
    "text": "PostgreSQL is a relational database known for ACID compliance, transactional integrity, and advanced SQL capabilities.",
    "metadata": {
      "category": "database",
      "topic": "postgresql",
      "difficulty": "beginner"
    }
  },
  {
    "text": "Celery is a distributed task queue system used to execute asynchronous background jobs in Python applications.",
    "metadata": {
      "category": "backend",
      "topic": "celery",
      "difficulty": "intermediate"
    }
  },
  {
    "text": "Apache Kafka is an event-streaming platform designed for building real-time data pipelines and distributed messaging systems.",
    "metadata": {
      "category": "streaming",
      "topic": "kafka",
      "difficulty": "advanced"
    }
  },
  {
    "text": "Vector databases store embedding vectors and enable semantic similarity search for AI-powered applications.",
    "metadata": {
      "category": "ai",
      "topic": "vector-db",
      "difficulty": "intermediate"
    }
  },
  {
    "text": "Idempotency ensures that repeated API requests produce the same result without causing duplicate operations or transactions.",
    "metadata": {
      "category": "fintech",
      "topic": "idempotency",
      "difficulty": "advanced"
    }
  },
  {
    "text": "WebSockets provide persistent bidirectional communication channels for realtime messaging and live updates.",
    "metadata": {
      "category": "backend",
      "topic": "websocket",
      "difficulty": "intermediate"
    }
  },
  {
    "text": "Docker allows developers to package applications and dependencies into lightweight portable containers.",
    "metadata": {
      "category": "devops",
      "topic": "docker",
      "difficulty": "beginner"
    }
  },
  {
    "text": "Kubernetes automates container deployment, scaling, orchestration, and infrastructure management across clusters.",
    "metadata": {
      "category": "devops",
      "topic": "kubernetes",
      "difficulty": "advanced"
    }
  },
  {
    "text": "Snowflake is a cloud-native data warehouse platform optimized for scalable analytics and data engineering workloads.",
    "metadata": {
      "category": "data-engineering",
      "topic": "snowflake",
      "difficulty": "intermediate"
    }
  },
  {
    "text": "Apache Airflow is a workflow orchestration platform used to schedule and monitor ETL and data pipelines.",
    "metadata": {
      "category": "data-engineering",
      "topic": "airflow",
      "difficulty": "intermediate"
    }
  },
  {
    "text": "Semantic caching stores previously generated LLM responses based on embedding similarity to reduce API cost and latency.",
    "metadata": {
      "category": "ai",
      "topic": "semantic-caching",
      "difficulty": "advanced"
    }
  },
  {
    "text": "Large Language Models are neural networks trained on massive datasets to generate human-like text and reasoning.",
    "metadata": {
      "category": "ai",
      "topic": "llm",
      "difficulty": "beginner"
    }
  },
  {
    "text": "Retrieval-Augmented Generation combines vector search with language models to improve contextual AI responses.",
    "metadata": {
      "category": "ai",
      "topic": "rag",
      "difficulty": "advanced"
    }
  },
  {
    "text": "SQLAlchemy is a Python ORM and database toolkit used for interacting with relational databases using Python objects.",
    "metadata": {
      "category": "backend",
      "topic": "sqlalchemy",
      "difficulty": "intermediate"
    }
  },
  {
    "text": "JWT tokens are digitally signed credentials used for stateless authentication and authorization in APIs.",
    "metadata": {
      "category": "security",
      "topic": "jwt",
      "difficulty": "beginner"
    }
  },
  {
    "text": "Rate limiting controls how many requests a client can make within a period to prevent abuse and overload.",
    "metadata": {
      "category": "security",
      "topic": "rate-limiting",
      "difficulty": "intermediate"
    }
  },
  {
    "text": "Pinecone is a managed vector database service optimized for low-latency semantic search and AI retrieval systems.",
    "metadata": {
      "category": "ai",
      "topic": "pinecone",
      "difficulty": "intermediate"
    }
  },
  {
    "text": "Event-driven architecture enables services to communicate asynchronously through events and message brokers.",
    "metadata": {
      "category": "architecture",
      "topic": "event-driven",
      "difficulty": "advanced"
    }
  }
]



  
  
toolbox = ToolBox(manager)
# meta = toolbox._get_tool_metadata(search_tavily)
# pprint(meta,indent=8)

@toolbox.register_tool(augment=True)
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
#print(inspect.signature(search_tavily))

