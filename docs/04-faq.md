# Questions a reviewer asks of an open-source manifest

This repository is an open-source project built on Kortix, the open-source AI Operating System. Eight questions come up in the first review of its manifest, and each section here answers one. Every answer names the mechanism, so a reviewer can check it against the reference instead of taking it on trust.

## Merging a change request

No. A session can merge its own change request only when its agent's `kortix_permissions` grant in `kortix.yaml` includes `project.gitops.merge` ([Kortix docs](https://kortix.com/docs)). Neither agent here holds it. The editor pushes its branch and opens the request. A person reads it and merges.

## Secrets inside the sandbox

A granted runtime secret is a real environment value in the session, and any command the agent runs can read it. Connector credentials are different, because they are brokered server-side and never enter the machine. Egress enforcement is the experimental middle case: the value stays outside the sandbox and is injected only for an approved HTTPS call. Environment is still the default ([Kortix docs](https://kortix.com/docs)). Both agents here hold `secrets: none`.

## The risk default

`policy.default_mode: risk` sets the decision for a connector call that no rule matches. A read runs. A write or destructive call needs approval. Under `allow_all`, which is the documented default, the call just runs ([kortix.yaml reference](https://kortix.com/docs/project/manifest)). This repository uses `risk` and adds two rules: any tool whose name starts with `delete` is blocked, and `send_email` waits for a person.

## A held call nobody answers

It waits for the window in `approvals.ttl`, then expires. The value is an integer with `m`, `h` or `d`, and Kortix clamps it to five minutes through thirty days. A missing value, or one written in another form, gives the 24-hour fallback, and nothing warns. A typo can shorten or lengthen the window silently. This repository sets `4h`.

## Widening an agent's own grants

It cannot. A merge that changes `agents` or `default_agent` needs `project.agent.write`. An agent session that writes a grant may add only what its own effective grant already holds, and narrowing is always allowed ([Agents & permissions](https://kortix.com/docs/project/agents)). An attempt to add more answers `403` with `agent_grant_escalation`. A person has to make the change.

## Validation and the policy block

`kortix validate` does not check `policy` or `policies` ([kortix.yaml reference](https://kortix.com/docs/project/manifest)). A malformed rule surfaces later, when Kortix syncs connectors, as a connector sync error. By then the merge has happened. `check_policy.py` reads those keys before that point, which is the reason the script exists.

## Two matching rules

The first match wins. Kortix checks the project-wide `policies` list before the connector's own `policies`. Each rule matches the fully qualified tool path, `<connector-slug>.<tool>`, with `*` globs. A rule can carry `conditions` that narrow it to calls whose arguments match, and every condition has to hold. Order the list from the narrowest rule to the broadest.

## The tool a sandbox cannot refuse

The sandbox decides where a command runs, and inside the machine a read and a send look the same to a shell. A policy rule in the repository decides the call itself, with three outcomes: run it, hold it for a person, or block it. That is why the sandbox and the grants get reviewed as two separate things.
