"""Local type shims for SQLAlchemy columns.

Phase 1 code was written expecting `TIMESTAMPTZ` to be importable from
`sqlalchemy.dialects.postgresql`, but SQLAlchemy 2.x does not export that
name. This module provides a drop-in subclass of `TIMESTAMP` that defaults
`timezone=True`, so existing `Column(TIMESTAMPTZ)` usage sites don't need
to change — only the import does.
"""
from sqlalchemy import TIMESTAMP as _TIMESTAMP


class TIMESTAMPTZ(_TIMESTAMP):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("timezone", True)
        super().__init__(*args, **kwargs)
