# An open-source sandbox policy you review as a diff

Kortix is the open-source CompanyOS, and this repository is a reference project built on it. A session runs in its own sandbox, and that sandbox bounds the damage a bad command can do. What decides whether the agent may attempt the command at all is the `kortix.yaml` in this repo: two agents with short grant lists, a policy mode set to `risk`, two rules and a four-hour approval window. Approval gates you set. Off until you set them.

The two agents here are deliberately weak. One edits the session branch and opens a change request; the other reads the diff and submits a review without a push. Neither holds the merge permission, and neither receives a connector or a secret. `check_policy.py` exists so that those claims get checked against the file instead of assumed.

## What is in here

| File | What it holds |
| --- | --- |
| `kortix.yaml` | Manifest: agents, grants, workspace, policy, rules, approval TTL |
| `agents/sandbox-editor.md` | Editing agent behaviour, as a prompt |
| `agents/policy-reviewer.md` | Reviewing agent behaviour, as a prompt |
| `check_policy.py` | Five review checks, including the policy keys validation skips |
| `docs/01-what-the-sandbox-decides.md` | Isolation against authority |
| `docs/02-five-checks.md` | The checker on a clean and a broken manifest |
| `docs/03-least-privilege-grants.md` | The two grant lists and the traps around them |
| `docs/04-faq.md` | The first questions a reviewer asks |

## The grant block

The editor's authority is four lines, and the merge is not among them. Its block reads:

```yaml
  sandbox-editor:
    file: agents/sandbox-editor.md
    enabled: true
    workspace:
      project_repository: true
    connectors: none
    secrets: none
    skills: none
    kortix_permissions:
      - project.read
      - project.file.read
      - project.gitops.read
      - project.gitops.push
```

`workspace: project_repository: true` gives the session a checkout of this repository on its own branch, which is what makes every edit a commit a reviewer can read. `connectors: none` and `secrets: none` are written out, because a grant that is absent resolves to none and a reviewer should not have to know that rule to read the file. The permission list ends at push: the agent can hand work over and cannot land it. The second agent, `policy-reviewer`, swaps `project.gitops.push` for `project.review.submit`, with the same repository access and no way to change it.

## Run the checker

```
python3 check_policy.py kortix.yaml
```

It needs PyYAML. It prints an error and warning count, then one blast-radius line per agent. On this manifest it reports `0 error(s), 0 warning(s)`. Drop a behaviour key into an agent block, or write `default_mode: sometimes`, and it fails with the line that names the key. `docs/02-five-checks.md` shows both runs with their real output.

## What the checker is not

`kortix validate` is the authority on the schema, and the same check runs in `kortix ship` and in the change request merge check. `check_policy.py` is a review aid that lives beside it: it reads the policy block, the rules and the approval window, which `kortix validate` does not check, and it prints what each agent can reach on one screen. Run both. When they disagree about the schema, believe `kortix validate`.

The policy model, the grant semantics and the limits of each key are documented in the [kortix.yaml reference](https://kortix.com/docs/project/manifest). The [agent sandboxing page](https://opensourceaiagentplatform.com/ai-agent-sandboxing) makes the argument in prose. The code is at [Kortix on GitHub](https://github.com/kortix-ai/suna). For the product itself, start at [Kortix](https://kortix.com).
