![chat ui](<iu/Screenshot 2026-05-25 053309.png>)


---
## 🧠 Mem Agent Summary

An advanced Medical AI Memory Agent system built with **FastAPI (backend)** and **React + TanStack Query (frontend)**. The system maintains long-term conversational memory across sessions using a multi-layer memory architecture (conversational, semantic, entity, and summary memory).

It intelligently manages context windows by summarizing long conversations, expanding relevant memory when needed, and retrieving past context to improve response accuracy and continuity.

The frontend uses TanStack Query for efficient server-state management, caching, and synchronization with the backend memory system.

## 🛠️ Tech Stack

### Frontend
- React
- TanStack Query
- TailwindCSS (optional)

### Backend
- FastAPI
- Pydantic
- PostgreSQL
- Pgvector
- Google Gemini
- Tavily API (for search tools)
- you can add and register new tool for the agent to use it

---

## ⚙️ Getting Started

### 📦 Prerequisites

Make sure you have installed:
- Pgvector 
- create vector extension
- documentation: https://github.com/pgvector/pgvector
---

## ⚙️ Backend Setup (FastAPI)

### 1. Clone repository


```bash
git clone https://github.com/owolabi-develop/MemAgent.git
cd backend
```

### 2. Create a .env file with the required variable
- GOOGLE_GEMINI_API_KEY
- DB_NAME
- TAVILY_API_KEY
- DB_PASSWORD
- DB_USER
- DB_HOST
- DB_PORT