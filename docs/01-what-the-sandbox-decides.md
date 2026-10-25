# What the sandbox decides, and what the file decides

A sandbox answers one question well: where a command runs. It does not decide what the agent may attempt. In a Kortix project, the open-source AI Operating System, those decisions sit in `kortix.yaml`. Keep the two mechanisms apart and the review gets shorter, because only one of them needs a line-by-line read.

## One machine, one branch, one identifier

A session runs one agent in its own sandbox. The sandbox clones the project repository and works on a new branch, named after the `session_id`, a UUID with no prefix ([Kortix docs](https://kortix.com/docs)). Two sessions share the repository and nothing else. No working tree, no installed packages, no uncommitted files pass between them.

That gives a run a clean floor. A coding agent that breaks its build, installs a conflicting dependency or leaves a decoded key in a directory leaves the mess on one machine. Only the commits and pushes travel, and the machine itself is disposable. One isolated sandbox per session. Each session has its own isolated machine and branch.

The isolation mechanism belongs to the compute provider, and it matters less than it sounds. Ask how strong the boundary is and the answer names a provider and a virtualisation technology. Ask what the agent may attempt and the same question returns nothing.

## The sandbox has no opinion about the tool call

Inside the machine, a connector call that reads a mailbox and one that sends a message look alike. A process starts, arguments go out, a zero exit code comes back. Nothing in the filesystem or the process table separates a read from a send. The machine sees one command exit zero either way.

Kortix puts the decision outside the machine. A rule per connector action sets whether the call executes, waits for a person or is refused. Rules match the fully qualified tool path, `<connector-slug>.<tool>`, with `*` globs, and the first match wins ([kortix.yaml reference](https://kortix.com/docs/project/manifest)). A call that no rule matches falls to `policy.default_mode`, whose documented default is `allow_all`.

This repository sets the mode to `risk` and writes two rules: block any tool whose name starts with `delete`, and hold any `send_email` call for approval. Those three lines are what a security reviewer can argue with. They are made of intent, and the machine only carries it out.

## Credentials the machine never sees

Connector credentials are brokered server-side and never enter the machine. A command that dumps the environment inside the sandbox finds no connector token in it. A compromised run has nothing to exfiltrate from that direction.

A runtime secret is a different object. A granted secret is a real environment value in the session, and any command the agent runs can read it. Egress enforcement narrows that for the secrets that support it: the sandbox holds a handle, and Kortix substitutes the real value outside the machine, only on approved HTTPS hosts. Environment remains the default exposure. Egress enforcement is experimental.

The practical rule for a grant list follows from the asymmetry. A secret an agent does not need is a value you cannot walk back once a session has read it. Rotating it is the only remedy.

## The branch is where the sandbox ends

Work leaves the machine as commits on the session branch. The agent pushes that branch and asks for a merge into the default branch. A person merges it. Merge is default-deny for agents.

The platform enforces this with a grant. A session can merge its own change request only when its agent's `kortix_permissions` grant in `kortix.yaml` includes `project.gitops.merge`. Both agents in this repository do without that permission, so the worst outcome of a bad session is a request a person rejects. The sandbox kept the damage local. The missing grant kept it from landing.

## What a reviewer is really approving

Three decisions sit outside the machine, and each one is a line in the same file:

| Decision | Where it is written | What this repository says |
| --- | --- | --- |
| Which connector calls may run | `policy` and `policies` | `risk`, plus block and approval rules |
| Whose credentials a call carries | `agents.<name>.secrets` | `none` on both agents |
| Whether work can reach main | `agents.<name>.kortix_permissions` | push and review, never merge |

The table is short because the decisions are few. A hosted sandbox product can be configured to match all three, and none of the three lives in the machine's own settings. They live in a file a person can read in one sitting, that git records, and that a change request shows as a diff.

That is why this repository ships a manifest. An image is reviewed once, when it is built, and drifts afterwards. A grants file is reviewed on every change, including the change where an agent's author quietly adds a permission.
