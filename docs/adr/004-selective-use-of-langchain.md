# ADR-004: Selective Use of LangChain

* **Status:** Accepted
* **Date:** 2026-08-17

## Context

The project is intended to demonstrate production-oriented AI engineering
rather than framework usage for its own sake.

LangChain provides useful abstractions for LLM integrations, retrieval,
prompts, tools, and related RAG functionality.

However, using LangChain for every part of the system would introduce
unnecessary abstraction and reduce control over core application behavior.

Document ingestion and chunking are core infrastructure and require
deterministic, testable behavior.

## Decision

LangChain will be used selectively where it provides meaningful value or
reduces implementation complexity.

LangChain will not be used for the core Markdown ingestion and chunking
pipeline.

Markdown parsing will use `markdown-it-py`, while the application's own
chunking logic will define the canonical chunking behavior.

LangChain may be introduced later for areas such as:

* LLM integration
* prompt and message abstractions
* retriever integrations
* tool interfaces
* other RAG components where its abstractions provide clear value

LangGraph may also be introduced later if the system requires stateful or
multi-step workflow orchestration.

## Rationale

Keeping core ingestion logic in the application provides direct control over
document structure, chunk boundaries, metadata, determinism, and testing.

Using LangChain selectively allows the project to benefit from its ecosystem
without introducing framework dependencies where straightforward Python code
is clearer and easier to maintain.

## Consequences

The project will contain some application-owned integration code instead of
delegating all RAG functionality to LangChain.

LangChain will not be a required dependency for the document ingestion
pipeline.

Future LangChain and LangGraph usage must be justified by a concrete
integration or orchestration requirement rather than by framework adoption
alone.
