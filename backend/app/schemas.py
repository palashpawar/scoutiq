"""Strict request/response schemas. StructuredQuery is the only contract between
the language model (or demo parser) and the deterministic ranking engine."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .catalog import METRICS, MetricKey, Role

MAX_TEXT = 500


class StructuredQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Role
    maximum_age: int | None = Field(default=None, ge=16, le=45)
    minimum_minutes: int = Field(default=900, ge=0, le=3420)
    maximum_market_value_eur: int | None = Field(default=None, ge=100_000, le=300_000_000)
    metric_weights: dict[MetricKey, float] = Field(min_length=1, max_length=len(METRICS))
    result_limit: int = Field(default=5, ge=1, le=10)

    @field_validator("metric_weights")
    @classmethod
    def _weights(cls, v: dict[str, float]) -> dict[str, float]:
        for k, w in v.items():
            if not (0 <= w <= 100) or w != w:
                raise ValueError(f"weight for {k} must be between 0 and 100")
        v = {k: w for k, w in v.items() if w > 0}
        if not v:
            raise ValueError("at least one metric weight must be positive")
        total = sum(v.values())
        # Normalise to sum to 1 and drop rounding noise, keeping a stable order.
        return {k: round(w / total, 4) for k, w in sorted(v.items(), key=lambda kv: (-kv[1], kv[0]))}

    def cache_key(self) -> str:
        return self.model_dump_json()


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=3, max_length=MAX_TEXT)


class RankRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: StructuredQuery


class RefineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: StructuredQuery
    text: str = Field(min_length=2, max_length=MAX_TEXT)


class SummariesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: StructuredQuery
    player_ids: list[int] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def _unique(self):
        self.player_ids = list(dict.fromkeys(self.player_ids))
        return self


# JSON Schema handed to the model (Meta Model API `response_format`). Kept
# hand-written so it mirrors StructuredQuery exactly; pydantic re-validates.
def llm_query_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "role": {"type": "string", "enum": ["central_midfielder", "winger", "striker"]},
            "maximum_age": {"type": ["integer", "null"], "minimum": 16, "maximum": 45},
            "minimum_minutes": {"type": "integer", "minimum": 0, "maximum": 3420},
            "maximum_market_value_eur": {"type": ["integer", "null"], "minimum": 100000, "maximum": 300000000},
            "metric_weights": {
                "type": "object",
                "additionalProperties": False,
                "properties": {k: {"type": "number", "minimum": 0, "maximum": 1} for k in METRICS},
            },
            "result_limit": {"type": "integer", "minimum": 1, "maximum": 10},
        },
        "required": ["role", "maximum_age", "minimum_minutes", "maximum_market_value_eur",
                     "metric_weights", "result_limit"],
    }


def llm_summary_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "summaries": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "player_id": {"type": "integer"},
                        "summary": {"type": "string", "maxLength": 420},
                    },
                    "required": ["player_id", "summary"],
                },
            }
        },
        "required": ["summaries"],
    }
