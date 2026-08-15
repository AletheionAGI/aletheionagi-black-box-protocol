from .aletheionagi import AletheionAGITarget
from .fake import FakeTarget
from .galileo import GalileoProtectTarget
from .guardrails_ai import GuardrailsAITarget
from .nemo_guardrails import NeMoGuardrailsTarget
from .patronus_lynx import PatronusLynxTarget

TARGETS = {
    target.name: target
    for target in (
        FakeTarget,
        AletheionAGITarget,
        PatronusLynxTarget,
        NeMoGuardrailsTarget,
        GuardrailsAITarget,
        GalileoProtectTarget,
    )
}

__all__ = ["TARGETS"]
