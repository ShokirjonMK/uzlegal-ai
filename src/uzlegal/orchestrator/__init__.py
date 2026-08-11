"""Orkestratsiya qatlami — router, debate, judge, gate (docs/01 § 2, 4-qatlam).

Bu paket agentlarni **bog'laydi**, lekin ularning ichini bilmaydi: rol
prompti, chiqish sxemasi va model chaqiruvi `uzlegal.agents` da qoladi.
Shu ajratish tufayli yangi rol qo'shish oqim kodiga tegmaydi.
"""

from uzlegal.orchestrator.debate import (
    DISAGREEMENT_THRESHOLD,
    citation_overlap,
    conclusion_distance,
    disagreement,
    needs_round_two,
)
from uzlegal.orchestrator.gate import (
    ClaimCheck,
    ClaimKind,
    ClaimStatus,
    GateReport,
    groundedness_gate,
    is_legal_claim,
    split_claims,
)
from uzlegal.orchestrator.graph import ConsultState, Deps, build_langgraph, run_consult
from uzlegal.orchestrator.router import ROLES_BY_MODE, Mode, RouteDecision, route
from uzlegal.orchestrator.trace import Trace, TraceEvent, new_trace_id

__all__ = [
    "DISAGREEMENT_THRESHOLD",
    "ROLES_BY_MODE",
    "ClaimCheck",
    "ClaimKind",
    "ClaimStatus",
    "ConsultState",
    "Deps",
    "GateReport",
    "Mode",
    "RouteDecision",
    "Trace",
    "TraceEvent",
    "build_langgraph",
    "citation_overlap",
    "conclusion_distance",
    "disagreement",
    "groundedness_gate",
    "is_legal_claim",
    "needs_round_two",
    "new_trace_id",
    "route",
    "run_consult",
    "split_claims",
]
