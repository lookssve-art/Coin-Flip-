"""Hilfsfunktionen (HTTP ohne externe Abhaengigkeit)."""

from .http import http_json, HttpError

__all__ = ["http_json", "HttpError"]
