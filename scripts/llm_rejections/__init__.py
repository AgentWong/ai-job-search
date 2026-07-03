"""Persistence for LLM-review per-position disqualifications.

The Python pre-filters already log their rejections to
results/tracking/data/ats_api_company_rejections.csv (aggregated counts).
LLM review agents, by contrast, only printed their disqualifications into the
session summary, so there was no durable record to audit which scoring-framework
categories were actually killing volume over time.

This module gives the LLM review agents a single static CLI to append their
per-position disqualifications to results/tracking/data/llm_rejections.csv,
so the data survives the run and can be rolled up on demand.
"""
