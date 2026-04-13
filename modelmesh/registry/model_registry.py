from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

# Columns allowed in dynamic UPDATE to prevent SQL injection
_ALLOWED_UPDATE_COLUMNS = frozenset({
    "provider", "context_window", "cost_per_1k",
    "is_default", "is_fallback", "enabled",
})


@dataclass
class ModelEntry:
    name: str
    provider: str
    context_window: int = 4096
    cost_per_1k_tokens: float = 0.0
    enabled: bool = True


class ModelRegistry:
    def __init__(self, config_path: Path):
        self._models: dict[str, ModelEntry] = {}
        self._defaults: dict[str, str] = {}
        self._config_path = config_path
        # Initial load from YAML (only used before DB is ready / for seeding)
        self._load(config_path)

    # ── YAML bootstrap (used for initial seed only) ───────────────────────────

    def _load(self, path: Path) -> None:
        if not path.exists():
            return
        data = yaml.safe_load(path.read_text())
        for name, attrs in data.get("models", {}).items():
            self._models[name] = ModelEntry(
                name=name,
                provider=attrs["provider"],
                context_window=attrs.get("context_window", 4096),
                cost_per_1k_tokens=attrs.get("cost_per_1k_tokens", 0.0),
            )
        self._defaults = data.get("defaults", {})

    # ── DB-backed operations ──────────────────────────────────────────────────

    async def load_from_db(self, db) -> None:
        """Replace in-memory state from DB (ALL rows — enabled and disabled).
        Call after startup and after any mutation.
        """
        rows = await db.fetch("SELECT * FROM models")
        self._models = {}
        default_name: Optional[str] = None
        fallback_name: Optional[str] = None
        for row in rows:
            self._models[row["name"]] = ModelEntry(
                name=row["name"],
                provider=row["provider"],
                context_window=row["context_window"],
                cost_per_1k_tokens=float(row["cost_per_1k"]),
                enabled=row["enabled"],
            )
            if row["is_default"] and row["enabled"]:
                default_name = row["name"]
            if row["is_fallback"] and row["enabled"]:
                fallback_name = row["name"]
        self._defaults = {}
        if default_name:
            self._defaults["chat"] = default_name
        if fallback_name:
            self._defaults["fallback"] = fallback_name

    async def add_model(
        self, db, name: str, provider: str, context_window: int,
        cost_per_1k: float, is_default: bool, is_fallback: bool,
    ) -> None:
        if is_default:
            await db.execute("UPDATE models SET is_default = FALSE")
        if is_fallback:
            await db.execute("UPDATE models SET is_fallback = FALSE")
        await db.execute(
            """
            INSERT INTO models (name, provider, context_window, cost_per_1k, is_default, is_fallback)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (name) DO UPDATE
              SET provider=$2, context_window=$3, cost_per_1k=$4,
                  is_default=$5, is_fallback=$6, enabled=TRUE, updated_at=now()
            """,
            name, provider, context_window, cost_per_1k, is_default, is_fallback,
        )
        await self.load_from_db(db)

    async def update_model(self, db, name: str, fields: dict) -> None:
        if not fields:
            return
        unknown = set(fields) - _ALLOWED_UPDATE_COLUMNS
        if unknown:
            raise ValueError(f"Unknown update columns: {unknown}")
        if fields.get("is_default"):
            await db.execute("UPDATE models SET is_default = FALSE")
        if fields.get("is_fallback"):
            await db.execute("UPDATE models SET is_fallback = FALSE")
        set_clauses = [f"{col} = ${i}" for i, col in enumerate(fields, start=1)]
        set_clauses.append("updated_at = now()")
        values = list(fields.values()) + [name]
        await db.execute(
            f"UPDATE models SET {', '.join(set_clauses)} WHERE name = ${len(values)}",
            *values,
        )
        await self.load_from_db(db)

    async def delete_model(self, db, name: str) -> None:
        await db.execute("DELETE FROM models WHERE name = $1", name)
        await self.load_from_db(db)

    # ── Read-only accessors ───────────────────────────────────────────────────

    def get(self, model_name: str) -> Optional[ModelEntry]:
        return self._models.get(model_name)

    def list_models(self) -> list[str]:
        """Returns only enabled models — used by the router for routing decisions."""
        return [name for name, e in self._models.items() if e.enabled]

    def list_all_models(self) -> list[str]:
        """Returns all models including disabled — used by the admin GET endpoint."""
        return list(self._models.keys())

    @property
    def default_chat_model(self) -> str:
        return self._defaults.get("chat", next(iter(self.list_models()), ""))

    @property
    def fallback_model(self) -> str:
        return self._defaults.get("fallback", self.default_chat_model)
