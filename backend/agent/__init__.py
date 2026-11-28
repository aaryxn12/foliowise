"""The AI layer: routes chat messages, calls planner tools, explains results.

planner/ never imports from here, so the deterministic engine works (and is
tested) without any LLM.
"""
