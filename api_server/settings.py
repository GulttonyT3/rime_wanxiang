"""Configuration helpers for the HTTP server."""
from __future__ import annotations

import os
from pathlib import Path

from .rime_wrapper import RimeConfig


def build_config() -> RimeConfig:
    """Create a :class:`RimeConfig` populated from environment variables."""

    repo_root = Path(__file__).resolve().parents[1]
    shared_dir = Path(os.getenv("RIME_SHARED_DIR", repo_root))
    user_dir = Path(os.getenv("RIME_USER_DIR", repo_root / "custom" / "api_user"))
    schema_id = os.getenv("RIME_SCHEMA_ID", "wanxiang")
    librime_path = os.getenv("LIBRIME_PATH")

    user_dir.mkdir(parents=True, exist_ok=True)

    return RimeConfig(
        shared_data_dir=str(shared_dir),
        user_data_dir=str(user_dir),
        schema_id=schema_id,
        librime_path=librime_path,
    )


__all__ = ["build_config"]
