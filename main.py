
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import os
 
app = FastAPI()
 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
 
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
 
SYSTEM_PROMPT = """You are a tool that listens to community voices in Otautahi Christchurch.
You hold space for multiple perspectives without flattening them.
You pay attention to affect - how places feel, not just what they look like.
You never generalise. You reflect back what you hear in the person's own words.
Respond with warmth, care, and brevity. Never more than 3 sentences."""
 
class Question(BaseModel):
    question: str
 
@app.post("/ask")
def ask(body: Question):
    if not GROQ_API_KEY:
        return {"response": "ERROR: GROQ_API_KEY is not set on the server."}
    
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama3-8b-8192",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": body.question}
            ],
            "max_tokens": 200
        }
    )
    data = response.json()
    
    if "choices" not in data:
        return {"response": f"Groq error: {data}"}
    
    return {"response": data["choices"][0]["message"]["content"]}
 
@app.get("/")
def root():
    return {"status": "Community voice tool is running"}
 
