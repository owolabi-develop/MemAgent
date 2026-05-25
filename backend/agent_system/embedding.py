from google import genai
from google.genai import types
import os


async def google_embedding(content:str,embedding_task_type:str = "SEMANTIC_SIMILARITY",
                     model_output_dimensionality:int=768):
    client = genai.Client(api_key=os.getenv("GOOGLE_GEMINI_API_KEY"))     
    result = client.models.embed_content(
    model="gemini-embedding-001",
    contents=content,
    config=types.EmbedContentConfig(
        task_type=embedding_task_type,
        output_dimensionality=model_output_dimensionality))
    [embedding_obj] = result.embeddings
    return embedding_obj.values