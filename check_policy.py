#!/usr/bin/env python3
"""Check a kortix.yaml for the things a reviewer actually has to read.

`kortix validate` catches schema errors. It explicitly does not check `policy` or
`policies` (the kortix.yaml reference says so), and it does not tell you what an
agent can reach in one place. This script adds the review checks on top:

  1. the file parses, and the version/default_agent wiring is sound
  2. every agent block carries only governance keys, and its grant sets are
     shaped like grant sets
  3. every permission named is a project permission, and no agent silently
     holds a plaintext `all`
  4. policy.default_mode, every policies rule and approvals.ttl are values the
     platform will not skip
  5. a blast-radius line per agent: repository access, connectors, secrets,
     permissions -- so the diff review is one screen

Usage:
    python3 check_policy.py [kortix.yaml] [--json]

Requires PyYAML. Exit codes: 0 clean (warnings allowed), 1 errors, 2 unreadable.
Documented behaviour it encodes is from https://kortix.com/docs/project/manifest
(read 2026-10-25).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - environment problem, not a manifest problem
    sys.exit("check_policy.py needs PyYAML: python3 -m pip install pyyaml")

# Governance keys a v2 agent block may carry. Behaviour (description, model,
# mode, permission, prompt, ...) belongs in the agent's .md, and the platform
# rejects it here.
AGENT_KEYS_V2 = {
    "file",
    "enabled",
    "connectors",
    "connectors_required",
    "connectors_personal",
    "secrets",
    "skills",
    "apps",
    "kortix_permissions",
    "kortix_cli",
    "tools",
    "sandbox",
    "workspace",
    "repository_access",
    "harnesses",
    "network_egress",
}

# Aliases the platform parses with a warning, and no-op entries that are errors.
PERMISSION_ALIASES = {
    "project.cr.open": "project.gitops.push",
    "project.cr.merge": "project.gitops.merge",
    "project.customize.read": "project.model.read",
    "project.customize.write": "project.settings.write",
}
PERMISSION_NOOPS = re.compile(
    r"^(project\.session\.exec|project\.gateway\.routing\.edit|project\.schedule\..*|project\.webhook\..*|channel\..*)$"
)

# Project permissions the platform documents. `kortix validate --scopes` prints
# the live list for your plan; this is the review-time copy.
PROJECT_PERMISSIONS = {
    "project.read",
    "project.write",
    "project.delete",
    "project.session.read",
    "project.session.start",
    "project.session.stop",
    "project.session.bindings.write",
    "project.members.read",
    "project.members.manage",
    "project.trigger.read",
    "project.trigger.create",
    "project.trigger.update",
    "project.trigger.delete",
    "project.trigger.fire",
    "project.agent.read",
    "project.agent.write",
    "project.skill.read",
    "project.skill.write",
    "project.command.read",
    "project.command.write",
    "project.file.read",
    "project.file.write",
    "project.settings.write",
    "project.sandbox.write",
    "project.model.read",
    "project.model.write",
    "project.gateway.logs.read",
    "project.gateway.spend.read",
    "project.gateway.budget.set",
    "project.gateway.keys.manage",
    "project.usage.read",
    "project.gitops.read",
    "project.gitops.push",
    "project.gitops.merge",
    "project.gitops.ref.any",
    "project.gitops.ref.delete",
    "project.secret.read",
    "project.secret.write",
    "project.connector.read",
    "project.connector.write",
    "project.connector.connections.manage",
    "project.app.read",
    "project.app.write",
    "project.app.deploy",
    "project.app.admin",
    "project.review.read",
    "project.review.submit",
    "project.review.act",
    "project.credentials.issue",
}

RULE_ACTIONS = {"always_run", "require_approval", "block"}
DEFAULT_MODES = {"allow_all", "risk"}
TTL_RE = re.compile(r"^(\d+)(m|h|d)$")
TTL_MIN, TTL_MAX = 5 * 60, 30 * 24 * 60 * 60  # platform clamp: 5 minutes .. 30 days


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.radius: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def grant_set(value) -> str | None:
    """Return a normalised description of a grant set, or None when malformed."""
    if value is None:
        return "none"
    if isinstance(value, str):
        if value in ("all", "*"):
            return "all"
        if value in ("", "none"):
            return "none"
        return None
    if isinstance(value, list):
        if not all(isinstance(v, str) for v in value):
            return None
        if "*" in value or "all" in value:
            return "all"
        return "none" if not value else f"{len(value)} named"
    return None


def ttl_seconds(raw: str) -> int | None:
    m = TTL_RE.match(str(raw))
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    return n * {"m": 60, "h": 3600, "d": 86400}[unit]


def check(path: Path, rep: Report) -> dict | None:
    try:
        doc = yaml.safe_load(path.read_text())
    except FileNotFoundError:
        rep.error(f"{path} does not exist")
        return None
    except yaml.YAMLError as exc:
        rep.error(f"{path} is not valid YAML: {exc}")
        return None
    if not isinstance(doc, dict):
        rep.error(f"{path} is not a mapping")
        return None

    # 1. version and default agent
    version = doc.get("kortix_version")
    if version not in (1, 2, 3):
        rep.error(f"kortix_version is {version!r}; it must be 1, 2 or 3")
    agents = doc.get("agents")
    if not isinstance(agents, dict) or not agents:
        rep.error("agents must be a non-empty map")
        agents = agents if isinstance(agents, dict) else {}
    default_agent = doc.get("default_agent")
    if version in (2, 3):
        if not default_agent:
            rep.error("default_agent is required in a v2/v3 manifest")
        elif default_agent not in agents:
            rep.error(f"default_agent {default_agent!r} is not a declared agent")
        elif isinstance(agents.get(default_agent), dict) and agents[default_agent].get("enabled") is False:
            rep.error(f"default_agent {default_agent!r} is disabled; a session naming no agent cannot start")

    if "runtime" in doc:
        rep.warn("runtime is deprecated and selects nothing; every new session runs pi")
    if "channels" in doc:
        rep.error("channels is removed in v2; reconnect channels from the dashboard")
    if isinstance(doc.get("sandbox"), dict):
        for key in ("image", "dockerfile", "slug", "cpu", "memory", "disk", "entrypoint", "context", "context_dir", "gpu"):
            if key in doc["sandbox"]:
                rep.error(f"sandbox.{key} is rejected in v2/v3; it belongs inside sandbox.templates")

    # 2 + 3. agent blocks
    for name, block in agents.items():
        if not re.match(r"^[a-z0-9][a-z0-9_-]{0,127}$", str(name)):
            rep.error(f"agent name {name!r} does not match [a-z0-9][a-z0-9_-]{{0,127}}")
        if not isinstance(block, dict):
            rep.error(f"agents.{name} is not a mapping")
            continue
        unknown = set(block) - AGENT_KEYS_V2
        if version in (2, 3) and unknown:
            rep.error(
                f"agents.{name} carries behaviour keys {sorted(unknown)}; in v2/v3 those live in the agent .md"
            )
        if version == 2:
            agent_file = block.get("file", f"agents/{name}.md")
            if not (path.parent / str(agent_file)).is_file():
                rep.error(f"agents.{name}.file {agent_file!r} does not exist next to {path.name}")

        shapes = {}
        for key in ("connectors", "secrets", "skills", "apps", "kortix_permissions"):
            shape = grant_set(block.get(key))
            if shape is None:
                rep.error(f"agents.{name}.{key} is not a grant set (all, none, or a list of names)")
                shape = "malformed"
            shapes[key] = shape
            if shape == "all" and key != "skills":
                rep.warn(f"agents.{name}.{key}: all -- write this as an explicit list and say why in the review")

        perms = block.get("kortix_permissions")
        if isinstance(perms, list):
            for p in perms:
                if not isinstance(p, str):
                    continue
                if p in PERMISSION_ALIASES:
                    rep.warn(f"agents.{name}: {p} is an alias of {PERMISSION_ALIASES[p]}; write the current permission")
                elif PERMISSION_NOOPS.match(p):
                    rep.error(f"agents.{name}: {p} is a no-op entry and is an error in v2/v3")
                elif p not in PERMISSION_ALIASES and p not in PROJECT_PERMISSIONS and p not in ("all", "*"):
                    rep.error(f"agents.{name}: {p!r} is not a project permission (kortix validate --scopes prints the list)")

        if "project.gitops.merge" in (perms or []) or perms in ("all", "*"):
            rep.warn(f"agents.{name} can merge its own change request (project.gitops.merge); a person is then not the gate")
        if shapes.get("secrets") == "all":
            rep.warn(f"agents.{name} receives every project secret as an environment value in its sandbox")

        workspace = block.get("workspace")
        repo_access = "project repository"
        if isinstance(workspace, dict) and workspace.get("project_repository") is False:
            repo_access = "no repository access"
        elif workspace == "runtime" or (version == 3 and workspace is None):
            repo_access = "no repository access"
        elif block.get("repository_access") is False:
            repo_access = "no repository access"
        rep.radius.append(
            f"{name}: {repo_access} | connectors={shapes.get('connectors')} | secrets={shapes.get('secrets')} "
            f"| permissions={shapes.get('kortix_permissions')}"
        )

    # 4. policy, policies, approvals
    policy = doc.get("policy") or {}
    if not isinstance(policy, dict):
        rep.error("policy is not a mapping")
        policy = {}
    mode = policy.get("default_mode", "allow_all")
    if mode not in DEFAULT_MODES:
        rep.error(f"policy.default_mode is {mode!r}; it must be allow_all or risk")
    elif mode == "allow_all":
        rep.warn("policy.default_mode is allow_all (the platform default): a connector call no rule matches just runs")

    rules = doc.get("policies") or []
    if not isinstance(rules, list):
        rep.error("policies is not a list")
        rules = []
    if not rules and mode == "allow_all":
        rep.warn("no policies and default_mode allow_all: nothing in this project is gated")
    for i, rule in enumerate(rules):
        where = f"policies[{i}]"
        if not isinstance(rule, dict):
            rep.error(f"{where} is not a mapping")
            continue
        match = rule.get("match")
        if not isinstance(match, str) or not match:
            rep.error(f"{where}.match must be a glob over <connector>.<tool>")
        action = rule.get("action")
        if action not in RULE_ACTIONS:
            rep.error(f"{where}.action is {action!r}; it must be one of {sorted(RULE_ACTIONS)}")
        for j, cond in enumerate(rule.get("conditions") or []):
            if not isinstance(cond, dict) or "arg" not in cond or "match" not in cond:
                rep.error(f"{where}.conditions[{j}] needs both arg and match")
            elif not isinstance(cond["match"], str):
                rep.error(f"{where}.conditions[{j}].match must be a glob string or /regex/")

    approvals = doc.get("approvals") or {}
    if not isinstance(approvals, dict):
        rep.error("approvals is not a mapping")
        approvals = {}
    if "ttl" in approvals:
        secs = ttl_seconds(approvals["ttl"])
        if secs is None:
            rep.error(f"approvals.ttl {approvals['ttl']!r} is not <int><m|h|d>; the call will wait 24h instead")
        elif not (TTL_MIN <= secs <= TTL_MAX):
            rep.error(f"approvals.ttl {approvals['ttl']!r} is outside the platform clamp (5m .. 30d)")

    return doc


def main(argv: list[str]) -> int:
    as_json = "--json" in argv
    args = [a for a in argv if not a.startswith("--")]
    path = Path(args[0]) if args else Path("kortix.yaml")
    rep = Report()
    doc = check(path, rep)
    if doc is None:
        if as_json:
            print(json.dumps({"valid": False, "path": str(path), "errors": rep.errors}, indent=2))
        else:
            for e in rep.errors:
                print(f"error: {e}")
        return 2 if not path.exists() else 1

    if as_json:
        print(
            json.dumps(
                {
                    "valid": not rep.errors,
                    "path": str(path),
                    "errors": rep.errors,
                    "warnings": rep.warnings,
                    "agents": rep.radius,
                },
                indent=2,
            )
        )
    else:
        print(f"{path}: {len(rep.errors)} error(s), {len(rep.warnings)} warning(s)")
        for e in rep.errors:
            print(f"  error:   {e}")
        for w in rep.warnings:
            print(f"  warning: {w}")
        print("what each agent can reach:")
        for line in rep.radius:
            print(f"  {line}")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
