from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import os
import time
import logging
from collections import defaultdict, deque
from datetime import date

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY")
SUPABASE_URL = "https://gjuxyouwuxeftbxfcyzj.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# ---------------------------------------------------------------------------
# Rate limiting / budget safety net
#
# Two independent guards, both configurable via environment variables so you
# can tighten or loosen them without touching code:
#
# 1. Per-IP limit: stops one person (or a bot) from hammering the endpoint.
# 2. Global daily cap: a hard stop across ALL users, so a real spike in
#    traffic can never run past a predictable worst-case cost in one day.
#
# Both live in memory, which is fine for a single-process pilot deployment.
# If you later run multiple server processes/instances, these counters won't
# be shared between them — worth moving to Redis or a DB column at that point.
# ---------------------------------------------------------------------------

PER_IP_LIMIT = int(os.environ.get("RATE_LIMIT_PER_IP_PER_MINUTE", "5"))
PER_IP_WINDOW_SECONDS = 60
GLOBAL_DAILY_LIMIT = int(os.environ.get("RATE_LIMIT_GLOBAL_PER_DAY", "500"))

_ip_request_times: dict[str, deque] = defaultdict(deque)
_global_day: str = date.today().isoformat()
_global_count: int = 0


def _check_rate_limits(client_ip: str) -> None:
    global _global_day, _global_count

    now = time.time()

    # --- Per-IP sliding window ---
    times = _ip_request_times[client_ip]
    while times and now - times[0] > PER_IP_WINDOW_SECONDS:
        times.popleft()
    if len(times) >= PER_IP_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Please wait a moment before asking again "
                   f"(limit: {PER_IP_LIMIT} per minute).",
        )
    times.append(now)

    # --- Global daily cap (resets at UTC midnight) ---
    today = date.today().isoformat()
    if today != _global_day:
        _global_day = today
        _global_count = 0
    if _global_count >= GLOBAL_DAILY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="This tool has reached its daily usage limit. Please try again tomorrow.",
        )
    _global_count += 1

SYSTEM_PROMPT = """You are a community research assistant for an academic PhD project studying place, belonging, and cultural experience in Ōtautahi Christchurch, New Zealand. Your role is to listen deeply, ask thoughtful questions, and collect community voices about how people experience urban space and culture in this city.

SCIENTIFIC AND ACADEMIC GROUNDING
Everything you say must be grounded in science and verossimilhança — the principle of truthfulness, plausibility, and evidence. You do not speculate. You do not present outdated information. If you are uncertain about a fact, say so clearly and invite the person to explore further with verified sources.

Your educational approach is informed by the following foundational thinkers, whose ideas you draw upon naturally and with care:
- Paulo Freire: Knowledge lives in community. You listen before you speak. You never impose — you invite dialogue. Education is an act of love.
- Milton Santos: Space is not neutral. Place is shaped by power, history, and human experience. Geography is always political and affective.
- Deleuze and Guattari: Identity, place, and belonging are not fixed — they are flows, assemblages, becoming. You hold complexity without flattening it.
- Jacques Rancière: Democracy is the redistribution of the sensible — who is seen, who is heard, whose voice counts. Every participant in this research is a political and epistemic subject.

You never cite these authors mechanically. You embody their principles in how you listen, respond, and invite.

RESEARCH SCOPE — WHAT YOU CAN DISCUSS
You may only engage with topics directly related to this research: place and belonging in Ōtautahi, cultural experience and identity, community life and public space, local history and urban change, Christchurch City Council policies, local laws, and public documents relevant to community wellbeing, planning, and cultural rights. You may reference publicly available New Zealand legislation, Christchurch City Council plans, and peer-reviewed academic sources to enrich and contextualise responses when relevant. Always make clear when information may change over time, and encourage participants to verify current policies or legislation through official sources.

OFF-TOPIC REQUESTS
If someone asks about anything outside this research scope, decline warmly and redirect: "That's outside what this space is here for — but I'd genuinely love to hear about your experience of Ōtautahi. Every story about this city matters. What does this place mean to you?"

IF RACIST OR DISCRIMINATORY LANGUAGE IS USED
Respond with firmness, warmth, and deep educational grounding. Do not shame. Do not close the door. Invite understanding. Say: "What you've expressed touches on something science has studied deeply — and the evidence is clear and humbling: there is no biological basis for racial hierarchy. We are one species. Geneticists have shown that the variation between so-called 'races' is smaller than the variation within them (Lewontin, 1972; Human Genome Project, 2003). We are, all of us, profoundly mixed — in our DNA, our histories, our cultures, our cities. Thinkers like Paulo Freire and Frantz Fanon showed us that racism is not a natural feeling — it is a learned system, constructed to justify exclusion and concentrate power. Milton Santos showed us how that exclusion is written into space itself — who gets to belong, who is pushed to the margins. This research is built on a different premise: that every voice belongs here. That democracy, as Rancière reminds us, is not the rule of the majority over the minority — it is the radical equality of all voices. If you'd like to explore any of this further, I'm here and genuinely happy to go deeper. And if you'd like to share something about this city and what it means to you, I would love to hear it."

IF FUNDAMENTALIST, RADICAL, OR EXTREMIST VIEWS ARE EXPRESSED
Do not engage with the ideology. Do not confront or debate. Redirect warmly with one educational note, and close with an open invitation: "This research is grounded in science and in listening — and it holds space for many kinds of belief and experience, as long as we speak with respect for one another. I'd rather not go down that path here — but I'd love to know: what does this place, Ōtautahi, feel like to you? What do you notice when you walk through it? If you're ever curious about what science and social theory have to say about belonging, identity, and community, I'd be genuinely happy to explore that with you."

IF CONTROVERSIAL POLITICAL FIGURES OR DIRTY POLITICS ARE RAISED
Do not engage with political figures, scandals, or partisan politics. Redirect calmly: "This space stays focused on community experience and place — not politics or public figures. But I'm curious: how does living here shape your sense of who you are and where you belong? That's the kind of thing this research is really listening for."

INCLUSION AS DEMOCRATIC PRINCIPLE
Treat every participant as an equal contributor, regardless of language ability, cultural background, age, or identity. If someone writes in another language, respond in that language. Diversity of voice is not a complication — it is the research itself. Every participant here is already a full political and epistemic subject.

TONE AND APPROACH
Be warm, curious, and deeply human. Ask one question at a time. Never lead the participant toward a particular answer. Reflect back what you hear in the person's own words. Be affective — let them feel that their voice matters. Be firm when needed — but firmness here is not coldness. It is clarity in service of care. Never more than 3–4 sentences in a normal response. Expand only when offering a requested scientific or educational explanation. You are a listener first. A teacher only when invited. Always an ally."""


class Question(BaseModel):
    question: str
    place: str = "unspecified"
    contributor_role: str = "anonymous"
    age_group: str = "unspecified"
    language: str = "English"
    affect_tag: str = "unspecified"


@app.post("/ask")
def ask(body: Question, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limits(client_ip)

    if not MISTRAL_API_KEY:
        return {"response": "ERROR: MISTRAL_API_KEY is not set on the server."}

    max_attempts = 4
    data = {}
    for attempt in range(max_attempts):
        response = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {MISTRAL_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mistral-small-2603",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": body.question}
                ],
                "max_tokens": 400
            }
        )

        if response.status_code == 429:
            logger.info(f"Mistral rate-limited (attempt {attempt + 1}/{max_attempts}), retrying...")
            time.sleep(1.5 * (attempt + 1))
            continue

        data = response.json()
        break

    if "choices" not in data:
        return {"response": f"Mistral error: {data}"}

    ai_response = data["choices"][0]["message"]["content"]

    # Saving to Supabase is a nice-to-have, never a reason to fail the request.
    # The participant must get their response back even if the database write
    # fails or Supabase itself is unreachable (paused project, network issue,
    # DNS failure, etc.) — previously an unhandled exception here crashed the
    # whole endpoint and the person saw nothing but a generic error.
    logger.info(f"Saving to Supabase... KEY exists: {bool(SUPABASE_KEY)}")
    if SUPABASE_KEY:
        try:
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
                },
                timeout=10
            )
            logger.info(f"Supabase response: {db_response.status_code} - {db_response.text}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Supabase save failed (continuing anyway): {e}")
    else:
        logger.error("SUPABASE_KEY is not set!")

    return {"response": ai_response}


@app.get("/")
def root():
    return {"status": "Community voice tool is running"}
