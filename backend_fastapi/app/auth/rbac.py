"""
Role-based access control (ported from Flask `app/auth/rbac.py`).

Use with FastAPI `Depends(...)` — see `app.api.deps.auth`.
"""

from __future__ import annotations

from app.api.deps.auth import admin_only, require_roles

__all__ = ["admin_only", "require_roles"]
