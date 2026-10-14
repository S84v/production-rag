"""Evaluation utilities for retrieval, generation, and answer scoring.

The two constants below are the shared failure representation used by the
evaluators when the RAG stream ends without a terminal event. The RAG contract
guarantees exactly one terminal ``complete`` or ``error`` event; its absence
means the stream was interrupted, so the example must be recorded as failed
rather than treated as a partial success.
"""

TERMINAL_EVENT_MISSING_CODE = "terminal_event_missing"
TERMINAL_EVENT_MISSING_MESSAGE = "The RAG stream ended without a terminal event."
