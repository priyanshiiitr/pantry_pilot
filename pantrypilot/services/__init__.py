"""Plain business logic shared by the API routes and (later) the agent tools.

DETERMINISTIC CODE: nothing in here is AI reasoning. Functions just read and write
the database in predictable ways. The AI agents call some of these same ideas
through tools in `pantrypilot/agents/tools/`, but the tools stay thin wrappers
around this code so there is exactly one place each rule lives.
"""
