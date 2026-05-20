import json
from embedding.embedding import google_embedding
class MemoryManager:
    """
    A simplified memory manager for AI agents using Oracle AI Database.
    
    Manages 7 types of memory:
    - Conversational: Chat history per thread (SQL table)
    - Tool Log: Raw tool execution outputs and metadata (SQL table)
    - Knowledge Base: Searchable documents (Vector store)
    - Workflow: Execution patterns (Vector store)
    - Toolbox: Available tools (Vector store)
    - Entity: People, places, systems (Vector store)
    - Summary: Storing compressed context window
    """
    
    def __init__(
        self,
        conn,
        conversation_table_name: str,
        knowledge_base_vs_name,
        workflow_vs_name,
        toolbox_vs_name,
        entity_vs_name,
        summary_vs_name,
        tool_log_table_name: str | None = None
    ):
        self.conn = conn
        self.conversation_table = conversation_table_name
        self.knowledge_base_vs = knowledge_base_vs_name
        self.workflow_vs = workflow_vs_name
        self.toolbox_vs = toolbox_vs_name
        self.entity_vs = entity_vs_name
        self.summary_vs = summary_vs_name
        self.tool_log_table = tool_log_table_name
        
        
    def write_conversational_memory(self, content: str, role: str, thread_id: str) -> str:
        
        with self.conn.cursor() as cur:
            
            cur.execute("""
            INSERT INTO conversational_memory
            (thread_id, role, content, metadata, con_timestamp)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id
        """, (thread_id, role, content, "{}",))
            
            record_id = cur.fetchone()[0]
        
        self.conn.commit()
        return record_id
    
    def read_conversational_memory(self,thread_id: str, limit: int = 10) -> str:
        
        with self.conn.cursor() as cur:
            
            cur.execute(f"""
                        SELECT content, role, con_timestamp FROM {self.conversation_table}
                        where thread_id = %s::varchar AND summary_id IS NULL ORDER BY con_timestamp ASC
                        FETCH FIRST %s ROWS ONLY """, (thread_id, limit))
            
            results = cur.fetchall()
            messages = [f"[{ts.strftime('%H:%M:%S')}] [{role}] {content}" for role, content, ts in results]
            messages_formatted = '\n'.join(messages)
            if not messages_formatted:
                messages_formatted = "(No unsummarized messages found for this thread.)"
            return f"""## Conversation Memory
                        ### What this memory is
                        Chronological, unsummarized messages from the current thread. This memory captures user intent, constraints, and commitments made in recent turns.
                        ### How you should leverage it
                        - Preserve continuity with prior decisions, terminology, and user preferences.
                        - Resolve references like "that", "previous step", or "the paper above" using earlier turns.
                        - If older context conflicts with newer user instructions, prioritize the latest user direction.
                        ### Retrieved messages

                        {messages_formatted}"""
    

    
    

    def mark_as_summarized(self, thread_id: str, summary_id: str):
        """Mark all unsummarized messages in a thread as summarized."""
        thread_id = str(thread_id)
        with self.conn.cursor() as cur:
            cur.execute(f"""
                UPDATE {self.conversation_table}
                SET summary_id = %s
                WHERE thread_id = %s AND summary_id IS NULL
            """, (summary_id, thread_id))
        self.conn.commit()
        print(f" Marked messages as summarized (summary_id: {summary_id})")
        
    def add_text_to_vs(self, table_name: str, content: str ,metadata:dict):
        embedding = google_embedding(content,model_output_dimensionality=1536)
        with self.conn.cursor() as cur:
            cur.execute(f"""
                        INSERT INTO {table_name} (content, metadata, embedding)
                        VALUES (%s, %s, %s) ON CONFLICT (id) DO UPDATE 
                        SET embedding = EXCLUDED.embedding;
                        """,(content, json.dumps(metadata),embedding))
        self.conn.commit()
        print(f"upserting document to table: {table_name}")
        
    def similarity_search_vs(self,table_name: str, query: str, k: int =3):
        ## similarity search for all vs method
        embedding = google_embedding(query,model_output_dimensionality=1536)
        with self.conn.cursor() as cur:
            cur.execute(f"""
                        SELECT content, metadata FROM {table_name}
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                        """,(embedding,k))
            result = cur.fetchall()
            return result
        
    def write_knowledge_base(self, text: str | list[str], metadata: dict | list[dict]):
        """
        Store knowledge-base content with metadata.

        Supports:
        - Single record: text=str, metadata=dict
        - Batch insert: text=list[str], metadata=list[dict]
        """
        if isinstance(text, list):
            texts = [str(t) for t in text]
            if isinstance(metadata, list):
                metadatas = metadata
            else:
                metadatas = [metadata for _ in texts]

            if len(texts) != len(metadatas):
                raise ValueError(
                    f"Knowledge-base batch length mismatch: {len(texts)} texts vs {len(metadatas)} metadata rows"
                )
            self.add_text_to_vs(self.knowledge_base_vs,texts, metadatas)
            return

        self.add_text_to_vs(self.knowledge_base_vs,[str(text)], [metadata if isinstance(metadata, dict) else {}])
        
    def write_toolbox(self,text:str, metadata: dict):
            """ write too details to db"""
            self.add_text_to_vs(self.toolbox_vs,text, metadata)
            return
        
    def read_toolbox(self, query: str, k: int = 3) -> list[dict]:
        """Find relevant tools and return google gemini-compatible schemas."""
        results = self.similarity_search_vs(self.toolbox_vs,query, k=k)
        tools = []
        seen_tool_names: set[str] = set()
        for _ , meta in results:
            tool_name = meta.get("name", "tool")
            if tool_name in seen_tool_names:
                continue
            seen_tool_names.add(tool_name)
            # Extract parameters from metadata and convert to OpenAI format
            stored_params = meta.get("parameters", {})
            properties = {}
            required = []
            
            for param_name, param_info in stored_params.items():
                # Convert stored param info to google gemini format schema format
                param_type = param_info.get("type", "string")
                # Map Python types to JSON schema types
                type_mapping = {
                    "<class 'str'>": "string",
                    "<class 'int'>": "integer", 
                    "<class 'float'>": "number",
                    "<class 'bool'>": "boolean",
                    "str": "string",
                    "int": "integer",
                    "float": "number",
                    "bool": "boolean"
                }
                json_type = type_mapping.get(param_type, "string")
                properties[param_name] = {"type": json_type}
                
                # If no default, it's required
                if "default" not in param_info:
                    required.append(param_name)
            
            tools.append({
                    "name": tool_name,
                    "description": meta.get("description", ""),
                    "parameters": {"type": "object", "properties": properties, "required": required}
             
            })
        return tools
    
    def read_knowledge_base(self, query: str, k: int = 3) -> str:
        """Search knowledge base for relevant content."""
        results = self.similarity_search_vs(self.knowledge_base_vs,query, k=k)
       
        content = "\n".join([doc[0] for doc in results])
        if not content:
            content = "(No relevant knowledge base passages found.)"
        return f"""## Knowledge Base Memory
                    ### What this memory is
                    Retrieved background documents and previously ingested reference material relevant to the current query.
                    ### How you should leverage it
                    - Ground responses in these passages when making factual or technical claims.
                    - Prefer concrete details from this memory over unsupported assumptions.
                    - If evidence is missing or ambiguous, state uncertainty and request clarification or additional retrieval.
                    ### Retrieved passages 
                    # {content}
                    # """
            