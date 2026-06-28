"""Append-only, hash-verketteter Audit-Log (GoBD: Unveraenderbarkeit)."""

from .audit_log import AuditLog, AuditRecord

__all__ = ["AuditLog", "AuditRecord"]
