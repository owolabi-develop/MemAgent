from fastapi import FastAPI,Form
from typing import Annotated
from fastapi.middleware.cors import CORSMiddleware
from agent_system.tools import register_common_tools
from agent_system.config import manager
from agent_system.call_agent import call_agent
import uuid

app = FastAPI(title="Mem Agent",
              summary="AI agent with advance memory with semantic tool management")

# CORS (Cross-Origin Resource Sharing) config
origins = [
    "http://localhost:5173",
    "http://localhost",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    register_common_tools()
    
    print("starting")




@app.get("/load-conversation")
def load_conversation():
    conversations = manager.load_conversational_memory_history()
    return {"conversation_history":conversations}

@app.post("/chat")
def chatAgent(user_query: Annotated[str, Form()]):
    thread_id = 5000
    res = call_agent(user_query,thread_id)
    return {"response":res}


