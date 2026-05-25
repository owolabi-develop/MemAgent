class StoreManager:
    """Manages all stores (vector stores and SQL tables) with getter methods for easy access."""
    
    async def __init__(self, client, table_names):
        """
        Initialize all stores.
        
        Args:
            client: postgres database connection
            embedding_function: Embedding model to use
            table_names: Dict with keys: knowledge_base, workflow, toolbox, entity, summary

        """
        self.client = client
     
        # Initialize all vector stores
        await self._knowledge_base_vs = self.create_vector_store(
            table_name=table_names['knowledge_base'],
        )
        
        await self._workflow_vs = self.create_vector_store(
            table_name=table_names['workflow'],
           
        )
        
        await self._toolbox_vs = self.create_vector_store(
            table_name=table_names['toolbox'],
        )
        
        await self._entity_vs = self.create_vector_store(
            table_name=table_names['entity'],
            
        )
        
        await self._summary_vs = self.create_vector_store(
            table_name=table_names['summary'],
        )
        
        ## initialize sql tables
        self._create_conversational_history_table = self.create_conversational_history_table()
        
        self._create_tool_log_table = self.create_tool_log_table()
        
        
    async def create_vector_store(self,table_name):
    
        with self.client.cursor() as cur:
           ## DROP TABLE IF EXISTS 
            try:
                cur.execute(f"DROP TABLE IF EXISTS {table_name}")
            except:
                pass
            cur.execute(f"""
                        CREATE TABLE {table_name} (
                            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                            content text NOT NULL,
                            metadata JSONB,
                            embedding vector(1536)
                             );
                        """)
        self.client.commit()
            
        print(f" Table {table_name} created successfully with indexes")
    async def create_tool_log_table(self,table_name: str = "TOOL_LOG_MEMORY"):
        """
        Create a table to store raw tool execution logs per thread.
        If the table already exists, returns the table name without recreating it.
        """
       
        with self.client.cursor() as cur:
            try:
                cur.execute(f"DROP TABLE IF EXISTS {table_name}")
            except:
                pass
            
            cur.execute(f"""
                CREATE TABLE {table_name} (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    thread_id VARCHAR(100) NOT NULL,
                    tool_call_id VARCHAR(200),
                    tool_name VARCHAR(200) NOT NULL,
                    tool_args JSONB,
                    result TEXT,
                    result_preview VARCHAR(2000),
                    status VARCHAR(30) DEFAULT 'success',
                    error_message TEXT,
                    metadata JSONB,
                    log_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute(f"""
                CREATE INDEX idx_{table_name.lower()}_thread_id ON {table_name}(thread_id)
            """)
            cur.execute(f"""
                CREATE INDEX idx_{table_name.lower()}_tool_name ON {table_name}(tool_name)
            """)
            cur.execute(f"""
                CREATE INDEX idx_{table_name.lower()}_log_timestamp ON {table_name}(log_timestamp)
            """)

        self.client.commit()
        print(f" Table {table_name} created successfully with indexes")
        
        return table_name

    async def create_conversational_history_table(self, table_name: str = "CONVERSATIONAL_MEMORY"):
        """
        Create a table to store conversational history.

        Args:
            conn: Oracle database connection
            table_name: Name of the table to create
        """
        with self.client.cursor() as cur:
            # Drop table if exists
            try:
                cur.execute(f"DROP TABLE IF EXISTS {table_name}")
            except:
                pass  # Table doesn't exist
            
            # Create table with proper schema
            cur.execute(f"""
                CREATE TABLE {table_name} (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    thread_id VARCHAR(100) NOT NULL,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    con_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    summary_id VARCHAR(100) DEFAULT NULL
                )
            """)
            
            # Create index on thread_id for faster lookups
            cur.execute(f"""
                CREATE INDEX idx_{table_name.lower()}_thread_id ON {table_name}(thread_id)
            """)
            
            # Create index on timestamp for ordering
            cur.execute(f"""
                CREATE INDEX idx_{table_name.lower()}_con_timestamp ON {table_name}(con_timestamp)
            """)
            
        self.client.commit()
        print(f"Table {table_name} created successfully with indexes")
        return table_name
            
    
   