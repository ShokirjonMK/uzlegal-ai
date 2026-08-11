"""Agent qatlami — rol promptlari va debate ishtirokchilari (docs/06).

Bu paket orkestratsiyani **bilmaydi**: agentlar bir-birini chaqirmaydi va
oqim haqida hech narsa bilmaydi. Kim kimdan keyin gapirishini
`uzlegal.orchestrator` hal qiladi (docs/12 § 2, 3-qoida).
"""

from uzlegal.agents.base import (
    SHARED_PREAMBLE,
    Agent,
    AgentContext,
    AgentError,
    AgentSchemaError,
    BaseAgent,
    build_prefix,
    extract_json,
    extract_tags,
    parse_sections,
)
from uzlegal.agents.roles import AGENT_CLASSES, ROLE_ORDER, get_agent
from uzlegal.agents.schemas import DoctrinalAnalysis, LegalFrame, Verdict

__all__ = [
    "AGENT_CLASSES",
    "ROLE_ORDER",
    "SHARED_PREAMBLE",
    "Agent",
    "AgentContext",
    "AgentError",
    "AgentSchemaError",
    "BaseAgent",
    "DoctrinalAnalysis",
    "LegalFrame",
    "Verdict",
    "build_prefix",
    "extract_json",
    "extract_tags",
    "get_agent",
    "parse_sections",
]
