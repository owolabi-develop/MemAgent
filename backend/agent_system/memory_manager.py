import json
from embedding import google_embedding
from google import genai
from google.genai import types
import os
from pydantic import BaseModel, Field
from typing import List, Optional,Literal

class Entity(BaseModel):
    name: str = Field(description="The name of the entity extracted.")
    type: Literal["PERSON", "PLACE", "SYSTEM"] = Field(description="The category of the entity.")
    description:str = Field(description="The brief description of the entity")
    

class EntitysModel(BaseModel):
    entities:List[Entity]
    
    
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
        self.llm_client = genai.Client(api_key=os.getenv('GOOGLE_GEMINI_API_KEY'))
        self.model = "gemini-3.5-flash"
        
        
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
        
    def similarity__with_filter_search_vs(self,table_name: str,query:str, filters: dict, k: int =3):
        embedding = google_embedding(query,model_output_dimensionality=1536)
        
        with self.conn.cursor() as cur:
            cur.execute(f"""
                        SELECT content, metadata FROM {table_name}
                        ORDER BY embedding <=> %s::vector
                        where metadata @> %s LIMIT %s
                        """,(embedding,filters,k))
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
        
    def write_summary(
        self,
        summary_id: str,
        full_content: str,
        summary: str,
        description: str,
        thread_id: str | None = None,
    ):
        """Store a summary with its original content."""
        metadata = {
            "id": summary_id,
            "full_content": full_content,
            "summary": summary,
            "description": description,
        }
        if thread_id is not None:
            metadata["thread_id"] = str(thread_id)
        self.add_text_to_vs(self.summary_vs,
            [f"{summary_id}: {description}"],
            metadata 
        )
        return summary_id
        
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
    
    
    ## read  and write tool logs
    
    def write_tool_log(
        self,
        thread_id: str,
        tool_name: str,
        tool_args,
        result: str,
        status: str = "success",
        tool_call_id: str | None = None,
        error_message: str | None = None,
        metadata: dict | None = None,
    ) -> str | None:
        """Persist raw tool execution logs for auditing and just-in-time retrieval."""
        if not self.tool_log_table:
            return None

        thread_id = str(thread_id)

        if isinstance(tool_args, (dict, list)):
            tool_args_str = json.dumps(tool_args, ensure_ascii=False)
        else:
            tool_args_str = "" if tool_args is None else str(tool_args)

        result_str = "" if result is None else str(result)
       
        preview = result_str.encode("utf-8")[:2000].decode("utf-8", errors="ignore")

        metadata_str = json.dumps(metadata, ensure_ascii=False) if metadata else "{}"

        with self.conn.cursor() as cur:
            cur.execute(f"""
                INSERT INTO {self.tool_log_table}
                    (thread_id, tool_call_id, tool_name, tool_args, result, result_preview, status, error_message, metadata, log_timestamp)
                VALUES
                    (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, {
                "thread_id": thread_id,
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "tool_args": tool_args_str,
                "result": result_str,
                "result_preview": preview,
                "status": status,
                "error_message": error_message,
                "metadata": metadata_str,
            })
            log_id = cur.fetchone()[0]

        self.conn.commit()
        return log_id

    def read_tool_logs(self, thread_id: str, limit: int = 20) -> list[dict]:
        """Read recent tool logs for a thread, newest first."""
        if not self.tool_log_table:
            return []

        thread_id = str(thread_id)
        with self.conn.cursor() as cur:
            cur.execute(f"""
                SELECT id, tool_call_id, tool_name, tool_args, result_preview, status, error_message, metadata, log_timestamp
                FROM {self.tool_log_table}
                WHERE thread_id = %s
                ORDER BY timestamp DESC
                FETCH FIRST %s ROWS ONLY
            """, {"thread_id": thread_id, "limit": limit})
            rows = cur.fetchall()

        logs = []
        for log_id, tool_call_id, tool_name, tool_args, result_preview, status, error_message, metadata, ts in rows:
            logs.append({
                "id": log_id,
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "tool_args": tool_args,
                "result_preview": result_preview,
                "status": status,
                "error_message": error_message,
                "metadata": metadata,
                "timestamp": ts.isoformat() if ts else None,
            })
        return logs
    
    def extract_entities(self, text: str, llm_client) -> list[dict]:
        """Use LLM to extract entities (people, places, systems) from text."""
        if not text or len(text.strip()) < 5:
            return []
        
        prompt = f'''Extract entities from: "{text[:500]}"Return JSON: If none: []'''

        try:
            response = llm_client.models.generate_content(
                model=self.model,
                messages=prompt,
                config=types.GenerateContentConfig(
                response_mime_type='application/json',
                response_schema=EntitysModel),
            )
            result = EntitysModel.model_validate_json(response.text).model_dump()
            
            return result
        except:
            return []
    
    def write_entity(self, name: str, entity_type: str, description: str, llm_client=None, text: str = None):
        """Store an entity OR extract and store entities from text."""
        if text and llm_client:
            # Extract and store entities from text
            entities = self.extract_entities(text, llm_client)
            for e in entities:
                self.add_text_to_vs(self.entity_vs,
                    [f"{e['name']} ({e['type']}): {e['description']}"],
                    [{"name": e['name'], "type": e['type'], "description": e['description']}]
                )
            return entities
        else:
            # Store single entity directly
            self.entity_vs.add_texts(
                [f"{name} ({entity_type}): {description}"],
                [{"name": name, "type": entity_type, "description": description}]
            )
    
    def read_entity(self, query: str, k: int = 5) -> str:
        """Search for relevant entities."""
        results = self.similarity_search_vs(self.entity_vs,query,k)
        if not results:
            return """## Entity Memory
### What this memory is
Entity-level context such as people, organizations, systems, tools, and other named items previously identified in conversations or documents.
### How you should leverage it
- Use entities to disambiguate references and maintain consistent naming.
- Preserve important attributes (roles, relationships, descriptions) across turns.
- Personalize and contextualize responses using relevant known entities.
### Retrieved entities
(No entities found.)"""
        
        entities = [f"• {doc.metadata.get('name', '?')}: {doc.metadata.get('description', '')}" 
                    for doc in results if hasattr(doc, 'metadata')]
        entities_formatted = '\n'.join(entities)
        return f"""## Entity Memory
### What this memory is
Entity-level context such as people, organizations, systems, tools, and other named items previously identified in conversations or documents.
### How you should leverage it
- Use entities to disambiguate references and maintain consistent naming.
- Preserve important attributes (roles, relationships, descriptions) across turns.
- Personalize and contextualize responses using relevant known entities.
### Retrieved entities

{entities_formatted}"""
    
    def write_summary(
        self,
        summary_id: str,
        full_content: str,
        summary: str,
        description: str,
        thread_id: str | None = None,
    ):
        """Store a summary with its original content."""
        metadata = {
            "id": summary_id,
            "full_content": full_content,
            "summary": summary,
            "description": description,
        }
        if thread_id is not None:
            metadata["thread_id"] = str(thread_id)
        self.add_text_to_vs(self.summary_vs,
            [f"{summary_id}: {description}"],
            [metadata]
        )
        return summary_id
    
    def read_summary_memory(self, summary_id: str, thread_id: str | None = None) -> str:
        """Retrieve a specific summary by ID (just-in-time retrieval)."""
        filters = {"id": summary_id}
        if thread_id is not None:
            filters["thread_id"] = str(thread_id)

        results = self.similarity__with_filter_search_vs(self.summary_vs,
            summary_id, 
            k=5, 
            filter=filters
        )
        if not results:
            if thread_id is not None:
                return f"Summary {summary_id} not found for thread {thread_id}."
            return f"Summary {summary_id} not found."
        doc = results[1]
        return doc.metadata.get('summary', 'No summary content.')
    
    def read_summary_context(self, query: str = "", k: int = 10, thread_id: str | None = None) -> str:
        """Get available summaries for context window (IDs + descriptions only)."""
        filters = None
        if thread_id is not None:
            filters = {"thread_id": str(thread_id)}
        results = self.similarity__with_filter_search_vs(self.summary_vs, query or "summary",filter=filters, k=k,)
        if not results:
            scope_note = ( 
                f"(No summaries available for thread {thread_id}.)"
                if thread_id is not None
                else "(No summaries available.)"
            )
            return """## Summary Memory
### What this memory is
Compressed snapshots of older conversation windows preserved to retain long-range context.
### How you should leverage it
- Use summaries to maintain continuity when full historical messages are not in the active context window.
- Call expand_summary(id) before depending on exact quotes, fine-grained details, or step-by-step chronology.
### Available summaries
""" + scope_note
        
        lines = [
            "## Summary Memory",
            "### What this memory is",
            "Compressed snapshots of older conversation windows preserved to retain long-range context.",
            "### How you should leverage it",
            "- Use summaries to maintain continuity when full historical messages are not in the active context window.",
            "- Call expand_summary(id) before depending on exact quotes, fine-grained details, or step-by-step chronology.",
            "### Available summaries",
            "Use expand_summary(id) to retrieve the detailed underlying conversation."
        ]
        if thread_id is not None:
            lines.append(f"Scope: thread_id = {thread_id}")
        for doc in results[0]:
            sid = doc.metadata.get('id', '?')
            desc = doc.metadata.get('description', 'No description')
            lines.append(f"  • [ID: {sid}] {desc}")
        return "\n".join(lines)
    
    def read_conversations_by_summary_id(self, summary_id: str) -> str:
        """
        Retrieve all original conversations that were summarized with a given summary_id.
        Returns conversations in order of occurrence with timestamps.
        
        Args:
            summary_id: The ID of the summary to expand
            
        Returns:
            Formatted string with original conversations and timestamps
        """
        with self.conn.cursor() as cur:
            cur.execute(f"""
                SELECT id, role, content, con_timestamp 
                FROM {self.conversation_table}
                WHERE summary_id = %s
                ORDER BY con_timestamp ASC
            """, {"summary_id": summary_id})
            results = cur.fetchall()
        
        if not results:
            return f"No conversations found for summary_id: {summary_id}"
        
        # Format conversations with timestamps
        lines = [f"## Expanded Conversations for Summary ID: {summary_id}"]
        lines.append(f"Total messages: {len(results)}\n")
        
        for msg_id, role, content, timestamp in results:
            ts_str = timestamp.strftime('%Y-%m-%d %H:%M:%S') if timestamp else "Unknown"
            lines.append(f"[{ts_str}] [{role.upper()}]")
            lines.append(f"{content}")
            lines.append("")  # Empty line between messages
        
        return "\n".join(lines)

            