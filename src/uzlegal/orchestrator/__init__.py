"""Orkestratsiya qatlami — maslahat oqimi, munozara, gate.

Tashqi dunyo bu paketni to'g'ridan-to'g'ri ishlatmaydi: yagona kirish
nuqtasi `uzlegal.core.consult()`. Bu yerdagi modullar shu funksiyaning
qismlari.
"""

from uzlegal.orchestrator.debate import disagreement, needs_second_round
from uzlegal.orchestrator.gate import GroundednessGate
from uzlegal.orchestrator.graph import build_context, run
from uzlegal.orchestrator.router import roles_for, route

__all__ = [
    "GroundednessGate",
    "build_context",
    "disagreement",
    "needs_second_round",
    "roles_for",
    "route",
    "run",
]
