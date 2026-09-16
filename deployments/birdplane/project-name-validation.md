# Project names and hyphens

Track retirement of this workaround in the
[upstream update checklist](upstream-update-checklist.md#project-display-names-containing-hyphens).

Investigated 2026-09-16 after MCP creation of `me-tracker-ts` returned HTTP 400.
The direct API response was `Project name cannot contain special characters.`
The MCP wrapper hid that known validation error behind a generic message.

## Upstream rationale

- [PR #8529](https://github.com/makeplane/plane/pull/8529), merged February 16,
  2026, introduced the shared special-character blacklist for names and ticket
  identifiers. Its description lists forbidden punctuation but does not list
  hyphens, although the committed regex includes them.
- [Issue #9280](https://github.com/makeplane/plane/issues/9280) reports hyphens
  being rejected on creation and rename. A maintainer acknowledged the bug;
  discussion was consolidated into #9226.
- In [this maintainer comment](https://github.com/makeplane/plane/issues/9226#issuecomment-4908346539),
  the stated motivation was a security practice concerning special-character
  encoding. The maintainer explicitly says hyphens and underscores can be
  permitted, and objects to removing all name validation.
- [PR #9341](https://github.com/makeplane/plane/pull/9341) proposes removing the
  name blacklist entirely. It was open and unmerged when checked. The maintainer
  says the team intends a more targeted fix.

The reviewed upstream discussion provides no specific technical dependency that
requires banning hyphens in display names. This is a conclusion about the sources
reviewed, not proof that every downstream integration accepts every character.

## Birdplane change

Give display names a separate blacklist that allows hyphens. Keep ticket-prefix
validation and every other existing name restriction. Apply it to public API
creation/update and browser API creation/update. Underscores were already allowed.
Translate the known upstream name-validation response into an MCP error naming
the `name` field, without exposing arbitrary response bodies.

## Verification

- 36 public/browser project API contract tests passed with the isolated
  `recurrence-test.yml` stack, `WEB_URL=http://localhost:3000`, and migrations
  enabled, including creating and renaming `me-tracker-ts` through both APIs.
- 33 MCP tests passed, including safe translation of the observed validation
  response and retaining generic errors for unrecognized upstream bodies.
- Ruff checks passed for the changed backend files and the MCP package.
- These changes have not been deployed to the live instance.
