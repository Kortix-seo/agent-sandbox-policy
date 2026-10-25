# An open-source grant list for least privilege

This repository is an open-source project built on Kortix, the open-source AI Operating System. A grant list is the shortest description of what an agent can do to your infrastructure. In a v2 manifest it is also the part that fails open by accident. Every grant is written out here, including the empty ones. The file then answers the question without the reader knowing a default.

## Three shapes, and the one that hides work

A grant set takes three forms, and the platform reads them the same way wherever it finds one. `all` (or `*`) grants everything. `none` (or `""` or an empty list) grants nothing. A list of names grants exactly those entries ([kortix.yaml reference](https://kortix.com/docs/project/manifest)). A list containing `*` means all, which is worth knowing before a reviewer reads a long list and assumes it is narrow.

The default changed with version 2. The reference puts it in five words for a v2 manifest: an omitted grant means none ([kortix.yaml reference](https://kortix.com/docs/project/manifest)). That covers `connectors`, `secrets`, `kortix_permissions` and `skills`. An agent that declares nothing reaches nothing. A new specialist starts locked down, and each grant is an addition someone chose.

That default is safe only if the diff is readable. `connectors: all` and `kortix_permissions: all` are single tokens that hand over a whole category. `kortix_permissions: all` means every project permission, including `project.members.manage` and `project.delete` ([Agents & permissions](https://kortix.com/docs/project/agents)). This repository uses neither, and the checker warns on both.

## The two agents, side by side

Both agents get a checkout of the repository on their own session branch. Past that the lists diverge by one entry each, which is the point. Authority is set per agent, not per project.

| Grant | sandbox-editor | policy-reviewer |
| --- | --- | --- |
| `project.read` | yes | yes |
| `project.file.read` | yes | yes |
| `project.gitops.read` | yes | yes |
| `project.gitops.push` | yes | no |
| `project.review.submit` | no | yes |
| `project.gitops.merge` | no | no |
| `connectors` | none | none |
| `secrets` | none | none |

The editor pushes and opens change requests, so it needs `project.gitops.push`. The reviewer reads the same diff and submits a review, so it needs `project.review.submit`. Neither can merge. A review the reviewer writes still waits for a person to act on it. A reviewer that could merge would make its own judgment final, and this two-agent arrangement would collapse into one agent with an opinion.

## Why merge stays out

Merge is a grant. A session can merge its own change request only when its agent's `kortix_permissions` grant in `kortix.yaml` includes `project.gitops.merge` ([Kortix docs](https://kortix.com/docs)). Session work reaches `main` through a change request. Merge is default-deny for agents.

Leaving the permission out is what turns the sandbox into a useful boundary on the path to production. A compromised or confused session can still push a branch, because that is how it delivers work. The branch sits in the repository where someone can read it. The merge is the step that makes the work real, and no agent in this repository can take it.

Granting it is a decision with a name. `project.gitops.merge` in a diff is easy to see, and `kortix validate --scopes` prints it among the grantable permissions when a reviewer wants the current spelling. A project that grants it to an agent has decided the agent's own review is enough. It should say so where people will read it.

## The entries that look like permissions and are not

Four retired spellings still parse. `project.cr.open` resolves to `project.gitops.push`, and `project.cr.merge` to `project.gitops.merge`. `project.customize.read` and `project.customize.write` resolve to the model, settings, sandbox and agent permissions they replaced. Each one validates with a warning. A diff containing `project.cr.merge` grants a merge to anyone who reads it as an alias for opening change requests, which the old name invites.

A second group is worse. `project.session.exec`, `project.gateway.routing.edit`, `project.schedule.*`, `project.webhook.*` and `channel.*` are no-op entries, and they are errors in v2 and v3. They look like capability and carry none. An agent whose list is padded with them has less authority than its author believed.

Three other keys are deprecated. `connectors_required` must be a subset of `connectors` and is not read at session start. `kortix_cli` is an alias of `kortix_permissions` and warns; giving both different values is an error. `workspace` written as the string `read` refuses session start outright with a `409`, so the boolean form is the only one worth committing.

## Grants change under review, not at runtime

An agent cannot hand itself a permission by writing one. A merge that changes `agents` or `default_agent` needs `project.agent.write`. An agent session that writes any agent's grant may add only what its own effective grant already holds, and narrowing is always allowed ([Agents & permissions](https://kortix.com/docs/project/agents)). An escalation attempt answers `403` with `agent_grant_escalation`. The fix is a person making the change.

That closes the loop this repository is built around. The sandbox limits what a bad session can touch. The grant list limits what it can attempt. The review of `kortix.yaml` is where both get decided. A reviewer who reads the four permission lines and the two `none` lines has read the whole of an agent's authority. A widening then arrives as a diff, in the open.
