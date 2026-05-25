from .embedding import google_embedding
import inspect
from pydantic import BaseModel, Field
from typing import List,Callable,Optional,Union
from google import genai
import os
from .memory_manager import MemoryManager
from google.genai import errors,types
import uuid




class ToolMetadata(BaseModel):
    """Metadata for a registered tool."""
    name: str
    description: str
    signature: str
    parameters: dict
    return_type: str
    
class GeneratedQuery(BaseModel):
    query:List[str] =  Field(description="list of diverse example queries")
    
    
    
class ToolBox:
    
     """
    A toolbox for registering, storing, and retrieving tools with LLM-powered augmentation.
    
    Tools are stored with embeddings for semantic retrieval, allowing the agent to
    find relevant tools based on natural language queries.
    """
     def __init__(self,memory_manager,model:str ="gemini-3.5-flash"):
        self.memory_manager = memory_manager
        self.model = model
        self._tools: dict[str, Callable] = {}
        self._tools_by_name: dict[str, Callable] = {}
        self.client = genai.Client(api_key=os.getenv("GOOGLE_GEMINI_API_KEY")) 
          
     async def _get_embedding(self,text: str) -> list[float]:
        embedding = await google_embedding(text,model_output_dimensionality=1532)
        return embedding
    
     async def _check_tool_exist_in_db(self,tool_name:str):
            with self.memory_manager.conn.cursor() as cur:
                cur.execute(f"""
                            SELECT count(*) FROM {self.memory_manager.toolbox_vs}
                            where metadata ->> 'name' = %s
                            """,(tool_name,))
             
                return cur.fetchone()[0] > 0
        
    
    
     async def _augment_docstring(
        self, docstring: str, source_code: str = ""
    ) -> str:
        """
        Use LLM to improve and expand a tool's docstring
        by analyzing both the original description and the
        function's source code.
        """
        
        if not docstring.strip() and not source_code.strip():
            return "No description provided."

        code_section = ""
        if source_code.strip():
            code_section = (
                "\n\nFunction source code:\n"
                f"```python\n{source_code}\n```"
            )

        prompt = (
            "You are a technical writer. "
            "Analyze the function's source code and its "
            "original docstring, then produce a richer, "
            "more detailed description. Include:\n"
            "1. A clear one-line summary\n"
            "2. What the function does step by step\n"
            "3. When an agent should call this function\n"
            "4. Important notes or caveats\n\n"
            f"Original docstring:\n{docstring}"
            f"{code_section}\n\n"
            "Return ONLY the improved docstring, "
            "no other text."
        )
        
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )

        return response.text.strip()
    
     async def _generate_queries(self, docstring: str, num_queries: int = 5) -> list[str]:
         """
            Generate synthetic example queries that would lead to using this tool.
         """
         prompt = f"""Based on the following tool description,
                generate {num_queries} diverse example queries
                that a user might ask when they need this tool. Make them natural and varied.

                Tool description:
                {docstring}

                Return ONLY a JSON array of strings, like: ["query1", "query2", ...]
            """
         
         try:
             
            response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                    response_schema=GeneratedQuery)
                    )
            queries = GeneratedQuery.model_validate_json(response.text)
            return queries.model_dump()
            
         except (errors.APIError, errors.ClientError, errors.ServerError) as e:
             return "error"
         
    
    
     async def _get_tool_metadata(self, func: Callable) -> ToolMetadata:
        """
        Extract metadata from a function for storage and retrieval.
        """
        sig = inspect.signature(func)
        
        # Extract parameter info
        parameters = {}
        
        for name, param in sig.parameters.items():
            param_info = {"name": name}
            if param.annotation != inspect.Parameter.empty:
                param_info["type"] = str(param.annotation)
            if param.default != inspect.Parameter.empty:
                param_info["default"] = str(param.default)
            parameters[name] = param_info
        
        # Extract return type
        return_type = "Any"
        if sig.return_annotation != inspect.Signature.empty:
            return_type = str(sig.return_annotation)
        
        return ToolMetadata(
            name=func.__name__,
            description=func.__doc__ or "No description",
            signature=str(sig),
            parameters=parameters,
            return_type=return_type
        )
    
     async def register_tool(
        self, func: Optional[Callable] = None, augment: bool = False
    ) -> Union[str, Callable]:
        """
        Register a function as a tool in the toolbox.

        If a tool with the same name already exists in the database,
        the callable is registered in memory but no duplicate row is
        written to the vector store.
        """

        async def decorator(f: Callable) -> str:
            
            tool_name = f.__name__
            ## check if tool name already in db
            too_ins = self._check_tool_exist_in_db(tool_name)
            if too_ins:
                self._tools_by_name[tool_name] = f
                return tool_name
            
            docstring = f.__doc__ or ""
            signature = str(inspect.signature(f))
            object_id = uuid.uuid4()
            object_id_str = str(object_id)

            if augment:
                # Use LLM to enhance the tool's discoverability
                try:
                    source_code = inspect.getsource(f)
                except (OSError, TypeError):
                    source_code = ""
                augmented_docstring =await self._augment_docstring(
                    docstring, source_code
                )
                queries = await self._generate_queries(augmented_docstring)

                # Create rich embedding text combining all information
                embedding_text = f"{f.__name__} {augmented_docstring} {signature} {' '.join(queries)}"
                embedding = await self._get_embedding(embedding_text)

                tool_data = await self._get_tool_metadata(f)
                tool_data.description = augmented_docstring  # Use augmented description

                tool_dict = {
                    "_id": object_id_str,  # Use string, not UUID object
                    "embedding": embedding,
                    "queries": queries,
                    "augmented": True,
                    **tool_data.model_dump(),
                }
            else:
                # Basic registration without augmentation
                embedding = await self._get_embedding(f"{f.__name__} {docstring} {signature}")
                tool_data = await self._get_tool_metadata(f)

                tool_dict = {
                    "_id": object_id_str,  # Use string, not UUID object
                    "embedding": embedding,
                    "augmented": False,
                    **tool_data.model_dump(),
                }

            # Store the tool in the toolbox memory for retrieval
            # The embedding enables semantic search to find relevant tools
            await self.memory_manager.write_toolbox(
                f"{f.__name__} {docstring} {signature}",
                tool_dict
            )

            # Keep reference to the callable for execution
            self._tools[object_id_str] = f
            self._tools_by_name[f.__name__] = f  # Also store by name for easy lookup
            return object_id_str

        if func is None:
            return await decorator
        return await decorator(func)
        