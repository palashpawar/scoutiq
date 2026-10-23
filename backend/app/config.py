"""Server-side configuration from environment variables (and backend/.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader; real environment variables take precedence."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BACKEND_DIR / ".env")
_load_dotenv(BACKEND_DIR.parent / ".env")


@dataclass(frozen=True)
class Settings:
    meta_api_base_url: str = os.getenv("META_API_BASE_URL", "https://api.meta.ai/v1").rstrip("/")
    meta_api_key: str = os.getenv("META_API_KEY", "")
    meta_model: str = os.getenv("META_MODEL", "muse-spark-1.3")
    meta_reasoning_effort: str = os.getenv("META_REASONING_EFFORT", "low")
    meta_timeout_seconds: float = float(os.getenv("META_TIMEOUT_SECONDS", "25"))
    db_path: Path = Path(os.getenv("SCOUTIQ_DB_PATH", str(BACKEND_DIR / "data" / "scoutiq.db")))
    rate_limit_per_minute: int = int(os.getenv("SCOUTIQ_RATE_LIMIT_PER_MINUTE", "30"))
    force_demo_mode: bool = os.getenv("SCOUTIQ_DEMO_MODE", "").lower() in {"1", "true", "yes"}

    @property
    def llm_enabled(self) -> bool:
        return bool(self.meta_api_key) and not self.force_demo_mode


settings = Settings()
