"""Server-side authorization.

In AWS, API Gateway's JWT authorizer validates the Cognito access token
(signature, issuer, audience/client_id, expiry) and passes verified claims in
requestContext.authorizer.jwt.claims. In demo mode, the local dev server
validates its own signed demo session token and injects claims in the same
shape. Either way this module enforces that the caller is in the staff group.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import forbidden, unauthorized


@dataclass(frozen=True)
class Principal:
    user_id: str
    username: str
    display_name: str
    groups: tuple[str, ...]


def _parse_groups(raw) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, list):
        return tuple(str(g) for g in raw)
    text = str(raw).strip()
    if text.startswith("[") and text.endswith("]"):  # HTTP API flattens arrays to "[a b]"
        text = text[1:-1]
    return tuple(g.strip().strip('"') for g in text.replace(",", " ").split() if g.strip())


def principal_from_event(event: dict, config) -> "Principal":
    claims = (((event.get("requestContext") or {}).get("authorizer") or {}).get("jwt") or {}).get("claims")
    if not claims or not claims.get("sub"):
        raise unauthorized()
    groups = _parse_groups(claims.get("cognito:groups"))
    if config.staff_group not in groups:
        raise forbidden("Your account is not in the staff group. Ask an administrator for access.")
    username = claims.get("username") or claims.get("cognito:username") or claims["sub"]
    staff = {s["id"]: s for s in config.staff_directory}
    display = claims.get("name") or (staff.get(username) or {}).get("name") or username
    return Principal(user_id=claims["sub"], username=username, display_name=display, groups=groups)
