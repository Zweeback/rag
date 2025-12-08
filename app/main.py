"""Backend für den DeepSeek Ping-Pong Chat."""

import os
from typing import Dict, List, Literal, Optional, Tuple

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
DEFAULT_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEFAULT_SYSTEM_PROMPT = os.getenv("DEEPSEEK_SYSTEM_PROMPT")
TIMEOUT_SECONDS = float(os.getenv("DEEPSEEK_API_TIMEOUT", "60"))
TEMPERATURE = float(os.getenv("DEEPSEEK_TEMPERATURE", "0.7"))
MAX_OUTPUT_TOKENS = _env_int("DEEPSEEK_MAX_OUTPUT_TOKENS", 1024)
MAX_MESSAGE_LENGTH = _env_int("DEEPSEEK_MAX_MESSAGE_LENGTH", 4000)
MAX_HISTORY_TURNS = _env_int("DEEPSEEK_MAX_HISTORY_TURNS", 12)

app = FastAPI(title="DeepSeek Ping-Pong Chat")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


class ChatTurn(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class UsageStats(BaseModel):
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

    model_config = ConfigDict(extra="ignore")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)
    history: List[ChatTurn] = Field(default_factory=list)
    system_prompt: Optional[str] = Field(default=None, max_length=MAX_MESSAGE_LENGTH)


class ChatResponse(BaseModel):
    reply: str
    history: List[ChatTurn]
    model: str = DEFAULT_MODEL
    usage: Optional[UsageStats] = None


def _api_key() -> str:
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="DEEPSEEK_API_KEY ist nicht gesetzt.")
    return key


def _limit_history(history: List[ChatTurn]) -> List[ChatTurn]:
    if MAX_HISTORY_TURNS <= 0:
        return history
    max_messages = MAX_HISTORY_TURNS * 2
    if max_messages <= 0 or len(history) <= max_messages:
        return history
    return history[-max_messages:]


def _prepare_messages(history: List[ChatTurn], user_message: str, system_prompt: Optional[str]) -> List[Dict[str, str]]:
    cleaned_history = _limit_history(history)
    message_turns: List[ChatTurn] = []
    prompt = (system_prompt or DEFAULT_SYSTEM_PROMPT or "").strip()
    if prompt:
        message_turns.append(ChatTurn(role="system", content=prompt))
    message_turns.extend(cleaned_history)
    message_turns.append(ChatTurn(role="user", content=user_message))
    def _model_dump(turn: ChatTurn) -> Dict[str, str]:
        if hasattr(turn, "model_dump"):
            return turn.model_dump()
        return turn.dict()

    return [_model_dump(turn) for turn in message_turns]


async def _call_deepseek(messages: List[Dict[str, str]]) -> Tuple[str, Optional[UsageStats]]:
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEFAULT_MODEL,
        "messages": messages,
        "stream": False,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_OUTPUT_TOKENS,
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.post(DEEPSEEK_API_URL, headers=headers, json=payload)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text) from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    data = response.json()
    try:
        text = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise HTTPException(status_code=500, detail="Unerwartetes DeepSeek-Antwortformat") from exc
    usage = data.get("usage")
    usage_stats = UsageStats(**usage) if isinstance(usage, dict) else None
    return text, usage_stats


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    message_text = request.message.strip()
    if not message_text:
        raise HTTPException(status_code=422, detail="Leere Nachrichten sind nicht erlaubt.")

    limited_history = _limit_history(request.history)
    api_messages = _prepare_messages(limited_history, message_text, request.system_prompt)
    reply_text, usage = await _call_deepseek(api_messages)

    updated_history = limited_history + [ChatTurn(role="user", content=message_text), ChatTurn(role="assistant", content=reply_text)]
    return ChatResponse(reply=reply_text, history=updated_history, usage=usage)


@app.get("/", response_class=FileResponse)
async def index() -> FileResponse:
    return FileResponse("app/static/index.html")


@app.get("/api/health")
async def health() -> JSONResponse:
    """Readiness-Route, die fehlende Pflicht-Settings meldet."""

    issues = []
    if not os.getenv("DEEPSEEK_API_KEY"):
        issues.append(
            {
                "name": "DEEPSEEK_API_KEY",
                "message": "Setze DEEPSEEK_API_KEY mit einem gültigen DeepSeek-API-Schlüssel.",
            }
        )
    if not DEEPSEEK_API_URL:
        issues.append(
            {
                "name": "DEEPSEEK_API_URL",
                "message": "DEEPSEEK_API_URL ist leer – konfiguriere die API-Endpoint-URL.",
            }
        )
    if not DEFAULT_MODEL:
        issues.append(
            {
                "name": "DEEPSEEK_MODEL",
                "message": "DEEPSEEK_MODEL ist leer – lege das gewünschte Modell fest.",
            }
        )

    payload: Dict[str, object] = {"status": "ok", "model": DEFAULT_MODEL or "unknown"}
    if DEFAULT_SYSTEM_PROMPT:
        payload["system_prompt"] = "preset"
    if issues:
        payload.update({"status": "error", "issues": issues})

    return JSONResponse(payload, status_code=200 if not issues else 503)
