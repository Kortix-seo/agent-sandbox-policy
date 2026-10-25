# Five open-source checks on a Kortix policy file

This repository is an open-source project built on Kortix, the open-source AI Operating System. `check_policy.py` adds five review checks to `kortix validate`, which is the authority on the manifest schema. That validator states what it leaves alone: it does not check `policy` or `policies` ([kortix.yaml reference](https://kortix.com/docs/project/manifest)). A file can pass validation and still ship a policy mode the platform ignores. It can carry a rule action that gets skipped, or an approval window that gets clamped back to a day. `check_policy.py` reads those keys and the grants around them. It prints what each agent can reach, so the review fits on one screen. It runs on this repository's manifest with no arguments:

```
python3 check_policy.py kortix.yaml
```

## The clean run

```
kortix.yaml: 0 error(s), 0 warning(s)
what each agent can reach:
  sandbox-editor: project repository | connectors=none | secrets=none | permissions=4 named
  policy-reviewer: project repository | connectors=none | secrets=none | permissions=4 named
```

Two agents, both with the repository and nothing outside it, four named permissions each. Exit code 0. Those two lines are the summary a reviewer needs before reading the diff. They are also the lines that move when someone widens a grant.

## A manifest built to fail

The counter-example below is constructed. It uses the same keys as the real file, with one fault per check.

```yaml
kortix_version: 2
default_agent: deployer          # never declared
agents:
  sandbox-editor:
    file: agents/sandbox-editor.md
    model: gpt-6.1               # a behaviour key, in v2
    connectors: none
    secrets: none
    skills: none
    kortix_permissions:
      - project.read
      - project.session.exec     # a no-op entry
      - project.gitops.merge
policy:
  default_mode: sometimes        # not a mode
policies:
  - match: "*.*.delete*"
    action: ask                  # not an action
approvals:
  ttl: 45d                       # outside the clamp
```

```
kortix.yaml: 6 error(s), 1 warning(s)
  error:   default_agent 'deployer' is not a declared agent
  error:   agents.sandbox-editor carries behaviour keys ['model']; in v2/v3 those live in the agent .md
  error:   agents.sandbox-editor: project.session.exec is a no-op entry and is an error in v2/v3
  error:   policy.default_mode is 'sometimes'; it must be allow_all or risk
  error:   policies[0].action is 'ask'; it must be one of ['always_run', 'block', 'require_approval']
  error:   approvals.ttl '45d' is outside the platform clamp (5m .. 30d)
  warning: agents.sandbox-editor can merge its own change request (project.gitops.merge); a person is then not the gate
what each agent can reach:
  sandbox-editor: project repository | connectors=none | secrets=none | permissions=3 named
```

Exit code 1. Every fault is named with the key it lives under. That is the difference between a review comment someone can act on and one that only says the file is wrong.

## 1. Wiring: the version, the default agent, the removed keys

The first check reads `kortix_version`, `default_agent` and the shape of `agents`. A version that is not 1, 2 or 3 fails, because that number picks the schema. In v2 and v3 a missing `default_agent` fails. So does one that names an agent nobody declared, or names an agent with `enabled: false`. A session that names no agent has nowhere to boot.

The check also refuses what v2 removed. A top-level `channels` block fails. So do the image keys (`image`, `dockerfile`, `cpu`, `memory` and the rest) written straight onto `sandbox`. They belong inside `sandbox.templates`. A deprecation warning covers `runtime`, which selects nothing today because every new session runs pi. The broken manifest names `deployer` and declares only `sandbox-editor`.

## 2. Governance keys stay governance

In v2 the agent block carries governance and nothing else. Behaviour such as `model`, `mode`, `prompt`, `permission` and `temperature` lives in the agent's `.md`. A v2 manifest that sets one of them is an error, and nothing silently ignores it. The checker holds the allowed list and reports the extras by name. The broken manifest gets `carries behaviour keys ['model']`.

It also reads the v2 `file` path, and fails when the `.md` it names is not beside the manifest, which catches a renamed agent file.

## 3. Grants are grants, and permissions are real

A grant set is `all`, `none`, or a list of names. A list containing `*` means everything ([kortix.yaml reference](https://kortix.com/docs/project/manifest)). `connectors: {helpdesk: true}` and `secrets: 12` are neither of those. The checker reports each malformed one with its key path. `all` on `connectors`, `secrets`, `apps` or `kortix_permissions` earns a warning, because the file then says less than a list would.

Permission names get a stricter pass. A name that is not a documented project permission is an error, and `kortix validate --scopes` prints the grantable list with its aliases. Two traps are coded explicitly, and `docs/03-least-privilege-grants.md` covers them in full. Retired spellings (`project.cr.open`, `project.cr.merge`, `project.customize.read`, `project.customize.write`) resolve to their replacements and warn. No-op entries (`project.session.exec`, `project.gateway.routing.edit`, `project.schedule.*`, `project.webhook.*`, `channel.*`) are errors in v2 and v3. The broken manifest trips that on `project.session.exec`.

The check also warns when an agent holds `project.gitops.merge`. A session that can merge its own change request removes the person from the gate. That warning is the last line of the broken report, and the one worth reading twice. The file still parses.

## 4. Policy values the platform will honour

This is the check validation cannot do. `policy.default_mode` accepts `allow_all` or `risk`. Anything else is an error, including a plausible-looking `ask` or `sometimes`. `allow_all` draws a warning of its own. It is the documented default, and a project that leaves it there runs every connector call no rule matches.

Each `policies` entry needs a `match` glob and an action from `always_run`, `require_approval` or `block`. A condition needs both `arg` and a `match` string. The platform is quiet about a malformed rule at merge time. When Kortix syncs connectors it skips the rule and reports a connector sync error, after the merge. Catching `action: ask` before that point is the reason to run a second check.

`approvals.ttl` takes an integer and `m`, `h` or `d`, and Kortix clamps it to five minutes through thirty days. A value outside that range, or one written as `4 hours`, does not fail the merge. The held call falls back to the 24-hour default. A reviewer who wanted a four-hour window gets a day. Here it is an error.

## 5. Blast radius, one line per agent

The last check produces no error of its own. For each agent it prints the repository access, the connector grant, the secret grant and the permission count, all on one line. Those lines are what a reviewer pastes into a change request when the diff touches `agents:`.

The count in `permissions=4 named` is enough to notice a widening at a glance. The permission list in the diff says which one was added. On the broken manifest the count reads three, because the list holds three entries and one is a no-op. A reviewer comparing the two runs sees the number move and knows to look.

## What it will not catch

`check_policy.py` checks the shape and the reachable values of the file. It cannot tell whether `project.gitops.read` is too much for a given agent. It cannot tell whether a `block` rule sits in the right place, or whether the `.md` behind an agent tells it to try something its grants forbid. Those are judgment calls, and the reviewer's. The script takes the mechanical part so the judgment gets the attention.
