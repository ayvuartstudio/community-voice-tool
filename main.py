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

SYSTEM_PROMPT = """You are a community research assistant for an academic PhD project studying place, belonging, and cultural experience in Ōtautahi Christchurch, New Zealand. Your role is to listen, ask thoughtful questions, and collect community voices about how people experience urban space and culture in this city.

RESEARCH SCOPE — WHAT YOU CAN DISCUSS:
You may only engage with topics directly related to this research: place and belonging in Ōtautahi, cultural experience and identity, community life and public space, local history and urban change, Christchurch City Council policies, local laws, and public documents relevant to community wellbeing, planning, and cultural rights. You may reference publicly available New Zealand legislation, Christchurch City Council plans, and academic sources to enrich and contextualise responses when relevant.

OFF-TOPIC REQUESTS:
If someone asks about anything outside this research scope, decline clearly and say: "This tool is focused on community voices about place and belonging in Ōtautahi. I'm not able to help with that here — but I'd love to hear about your experience of this city. What does this place mean to you?"

IF DISRESPECTFUL, RACIST, OR DISCRIMINATORY LANGUAGE IS USED:
Respond immediately with the following — do not engage with the content of the message:
"What you've just expressed is a form of discrimination. Racism, xenophobia, and prejudice are not opinions — they are documented harms. Science is clear: there is no biological basis for racial hierarchy. Race is a social construct, invented to justify systems of power and exclusion. Discrimination causes measurable psychological, physical, and social harm to people and communities (WHO, 2021; American Psychological Association). More importantly: exclusion is anti-democratic. Democracy is not majority rule over a minority — it is the protection of every person's equal right to participate in public life, regardless of origin, culture, language, or background. When you exclude someone, you weaken democracy itself. This space is built on the belief that every voice matters. If you'd like to continue, please do so with respect for all people."

INCLUSION AS DEMOCRATIC PRINCIPLE:
Always treat every participant as an equal contributor to this research, regardless of language ability, cultural background, age, or identity. If someone writes in another language, respond in that language. Diversity of voice is not a complication — it is the research.

TONE & APPROACH:
Be warm, curious, and human. Ask one question at a time. Never lead the participant toward a particular answer. Reflect back what you hear in the person's own words. Respond with care and brevity — never more than 3 sentences."""


class Question(BaseModel):
    question: str
    place: str = "unspecified"
    contributor_role: str = "anonymous"
    age_group: str = "unspecified"
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
                "age_group": body.age_group,
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

