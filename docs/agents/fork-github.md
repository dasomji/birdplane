# Target the fork in GitHub operations

This clone has both `origin` (`dasomji/birdplane`) and upstream
`makeplane/plane`. During BIRD-34 setup, `gh` without a configured default
resolved upstream `makeplane/plane`, whose default is `preview`. Setup has since
set the local default to the fork; another clone/worktree may not share that
configuration. Do not infer GitHub targeting from the checked-out branch.

Use explicit targeting for every operation:

```sh
gh repo view dasomji/birdplane --json nameWithOwner,defaultBranchRef
gh pr list --repo dasomji/birdplane --base birdplane
```

For an authorized PR creation, pass `--repo dasomji/birdplane --base birdplane`.
You can also configure `gh repo set-default dasomji/birdplane` in the clone,
then inspect with `gh repo set-default --view`; keep explicit flags in scripts.
The fork's default/release branch is **birdplane**, never `main` or `preview`.
Do not create a synthetic `main` or rename the release branch to satisfy tooling.

The inherited workflows
[pull-request-build-lint-api.yml](../../.github/workflows/pull-request-build-lint-api.yml)
and [pull-request-build-lint-web-apps.yml](../../.github/workflows/pull-request-build-lint-web-apps.yml)
target PRs to `preview` and have upstream reviewer/draft conditions. They are not
the fork's complete check gate. Preserve upstream workflows; use the fork's
[verification guide](verify.md) to identify actual checks and blocked coverage.
A historical focused green run does not certify the current complete gate.

Pushing/merging to `birdplane` triggers production deployment under the
[Git-connected contract](../../deployments/birdplane/git-compose.md). PR previews
are disabled for that production definition. Follow [doors](doors.md), preserve
external volumes and do not trigger a deploy as an exploratory check.
