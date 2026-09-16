"""Stub AWS Bedrock AgentCore Runtime entrypoint for PantryPilot.

NOT needed to run PantryPilot locally — the worker (pantrypilot/worker/jobs.py)
calls runner.run_case()/resume_case() directly. This file only matters if
actually deploying to AgentCore Runtime (see ../docs/aws-deployment.md for the
full component mapping).

AgentCore Runtime expects one function, decorated with @app.entrypoint, that
takes a JSON-shaped payload and returns a JSON-shaped result. Everything below
just adapts that shape onto the exact same run_case/resume_case functions the
worker already uses — no agent, tool, or prompt code changes for deployment.

Requires the `bedrock-agentcore` package (not installed by default — see
requirements.txt; add it only when actually deploying).
"""

from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp

from pantrypilot.agents.console import ensure_utf8_console
from pantrypilot.agents.runner import resume_case, run_case
from pantrypilot.database import create_tables

ensure_utf8_console()
create_tables()

app = BedrockAgentCoreApp()


@app.entrypoint
def handler(payload: dict[str, Any]) -> dict[str, Any]:
    """Run or resume one case, the same way EventBridge would trigger it.

    Expected payload shapes (matching worker/jobs.py's two call sites):
        {"action": "run_case", "offer_id": 123, "trigger": "new_offer"}
        {"action": "resume_case", "decision_id": 456}

    Returns the resulting CaseUpdate as a dict, or {"paused": True} if the
    Coordinator raised a human decision instead of finishing.
    """
    action = payload.get("action", "run_case")

    if action == "run_case":
        update = run_case(offer_id=payload["offer_id"], trigger=payload.get("trigger", "new_offer"))
    elif action == "resume_case":
        update = resume_case(decision_id=payload["decision_id"])
    else:
        raise ValueError(f"Unknown action '{action}'. Use 'run_case' or 'resume_case'.")

    return update.model_dump() if update is not None else {"paused": True}


if __name__ == "__main__":
    app.run()
