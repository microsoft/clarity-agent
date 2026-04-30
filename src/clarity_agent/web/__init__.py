"""
Clarity Agent web UI.

Provides a FastAPI application that serves the React frontend and exposes
WebSocket (chat) and REST (protocol, staleness, transcripts, packets) APIs.

Usage::

    from clarity_agent.web import create_app          # single-project server
    from clarity_agent.web import create_launcher     # multi-project launcher
"""

from clarity_agent.web.app import create_app
from clarity_agent.web.launcher import create_launcher

__all__ = ["create_app", "create_launcher"]
