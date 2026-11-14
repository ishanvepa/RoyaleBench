"""Visible loading feedback that always clears when work finishes or fails."""

from contextlib import contextmanager
from contextvars import ContextVar
from html import escape

import streamlit as st

_active = ContextVar("dashboard_loading", default=None)


def _markup(message):
    return ('<div class="rb-loading" role="status" aria-live="polite" aria-busy="true">'
            '<div class="rb-loading-card"><span class="rb-loading-spinner" aria-hidden="true"></span>'
            f'<span>{escape(message)}</span></div></div>')


@contextmanager
def loading(message="Loading..."):
    active = _active.get()
    if active is not None:
        placeholder, previous = active
        token = _active.set((placeholder, message))
        placeholder.html(_markup(message))
        try:
            yield
        finally:
            placeholder.html(_markup(previous))
            _active.reset(token)
        return
    placeholder = st.empty()
    token = _active.set((placeholder, message))
    placeholder.html(_markup(message))
    try:
        yield
    finally:
        placeholder.empty()
        _active.reset(token)
