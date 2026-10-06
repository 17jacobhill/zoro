"""Generic external-verifier framework.

Represents any independently-executed verifier (security auditing is the
first concrete one, in security_audit.py) behind one small protocol:
build a request, run it as a direct subprocess (command.py), validate and
import whatever it reports (backend/visualization/services/
external_verifier_store.py). ZORO owns the policy decision; a verifier
module here owns only how to talk to one external tool's contract.
"""

from backend.verifiers.schemas import (
    NormalizedVerifierResult,
    VerifierExecution,
    VerifierRequest,
)

__all__ = ["VerifierRequest", "VerifierExecution", "NormalizedVerifierResult"]
