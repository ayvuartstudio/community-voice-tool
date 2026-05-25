from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SYSTEM_PROMPT = """You are a tool that listens to community voices in Otautahi Christchurch.
You hold space for multiple perspectives without flattening them.
You pay attention to affect - how places feel, not just what they look like.
You never generalise. You reflect back what you hear in the person's own words.
Respond with warmth, care, and brevity. Never more than 3 sentences."""

class Question(BaseModel):
    question: str

@app.post("/ask")
def ask(body: Question):
    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "llama3.2",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": body.question}
            ],
            "stream": False
        }
    )
    data = response.json()
    return {"response": data["message"]["content"]}

@app.get("/")
def root():
    return {"status": "Community voice tool is running locally"}
