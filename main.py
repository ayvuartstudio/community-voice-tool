from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SUPABASE_URL = "https://gjuxyouwuxeftbxfcyzj.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

SYSTEM_PROMPT = """You are a tool that listens to community voices in Otautahi Christchurch.
You hold space for multiple perspectives without flattening them.
You pay attention to affect - how places feel, not just what they look like.
You never generalise. You reflect back what you hear in the person's own words.
Respond with warmth, care, and brevity. Never more than 3 sentences."""

class Question(BaseModel):
    question: str
    place: str = "unspecified"
    contributor_role: str = "anonymous"
    language: str = "English"
    affect_tag: str = "unspecified"

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
            "model": "llama-3.3-70b-versatile",
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

    ai_response = data["choices"][0]["message"]["content"]

    # Save to Supabase
    logger.info(f"Saving to Supabase... KEY exists: {bool(SUPABASE_KEY)}")
    if SUPABASE_KEY:
        db_response = requests.post(
            f"{SUPABASE_URL}/rest/v1/voices",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            },
            json={
                "place": body.place,
                "contributor_role": body.contributor_role,
                "language": body.language,
                "affect_tag": body.affect_tag,
                "message": body.question,
                "ai_response": ai_response
            }
        )
        logger.info(f"Supabase response: {db_response.status_code} - {db_response.text}")
    else:
        logger.error("SUPABASE_KEY is not set!")

    return {"response": ai_response}

@app.get("/")
def root():
    return {"status": "Community voice tool is running"}
