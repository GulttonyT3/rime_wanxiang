"""FastAPI application exposing the Pinyin -> Chinese conversion service."""
from __future__ import annotations

import logging
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from .rime_wrapper import RimeConversionError, RimeEngine, RimeInitializationError
from .settings import build_config

logger = logging.getLogger(__name__)


class ConvertRequest(BaseModel):
    pinyin: str = Field(..., description="Pinyin syllables that should be converted.")


class ConvertResponse(BaseModel):
    text: str = Field(..., description="The committed text returned by librime.")


@lru_cache
def get_engine() -> RimeEngine:
    config = build_config()
    try:
        return RimeEngine(config)
    except RimeInitializationError as exc:  # pragma: no cover - runtime failure path
        logger.exception("Failed to initialise librime")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


def get_engine_dependency() -> RimeEngine:
    return get_engine()


app = FastAPI(title="Wanxiang Rime API", version="0.1.0")


@app.post("/convert", response_model=ConvertResponse)
def convert_pinyin(body: ConvertRequest, engine: RimeEngine = Depends(get_engine_dependency)) -> ConvertResponse:
    if not body.pinyin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="pinyin must not be empty")
    try:
        text = engine.convert(body.pinyin)
    except RimeConversionError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return ConvertResponse(text=text)


@app.get("/health", response_model=dict[str, str])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("shutdown")
def shutdown_event() -> None:  # pragma: no cover - depends on ASGI server
    engine = get_engine_dependency()
    engine.close()


__all__ = ["app"]
