# Plane forum: Community Edition gaps

Scouted read-only on 2026-09-11 by three GPT-5.6 Sol agents. Dates below refer to staff statements or reports, not independent verification against every current edition. “Commercial” can include a free tier; it does not always mean a paid subscription. Forum announcements alone do not establish CE exclusion.

## Explicit edition or plan restrictions

| Feature                             | Forum evidence                                                                                                                                                                                                                                                | Date     |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- |
| Negative filters                    | Staff explicitly places `is not` on paid plans. Birdplane now implements it independently. [Thread](https://forum.plane.so/t/inverse-filtering-blocked-right-now-it-only-shows-is-option-it-should-also-show-at-least-is-not-when-filtering/285)              | July 27  |
| Relative-date queries / PQL         | Staff says PQL can express today/this-week queries and requires Pro or above. [Thread](https://forum.plane.so/t/allow-relative-dates-for-filters/284)                                                                                                         | July 28  |
| Official mobile app                 | Staff confirms no CE workaround: app is closed source and supports Cloud/Commercial; suggests web PWA. [Thread](https://forum.plane.so/t/alternative-mobile-app-compatible-with-self-hosted-version-community-edition/102)                                    | April 20 |
| ClickUp importer                    | Staff confirms absent from CE, available in Commercial Free and Cloud; Commercial Free had a 12-seat cap. [Thread](https://forum.plane.so/t/missing-clickup-import-in-self-hosted-community-edition-most-cost-effective-upgrade-path/95)                      | April 16 |
| Native desktop app for self-hosting | Announcement explicitly scopes macOS/Linux self-hosted support to Commercial. [Announcement](https://forum.plane.so/t/plane-commercial-v3-0-0-is-live-desktop-app-workspace-governance-rbac-and-more/281)                                                     | July 17  |
| Planned native start/stop timer     | Maintainer places planned timer in Business and above. August 4 follow-up reported it still unshipped. This does not establish the entitlement of manual time entries. [Thread](https://forum.plane.so/t/please-add-a-native-time-tracker/73)                 | April 10 |
| Importing Work Item Types           | Maintainer calls this an Enterprise Grid feature, separately from an Epic-creation API bug. [Reply](https://forum.plane.so/t/enabling-work-item-types-via-rest-api-silently-and-permanently-prevents-the-project-from-ever-having-the-native-epic-type/291/2) | August 5 |

## Delays and feature requests, not proven CE paywalls

- **Custom work-item relation APIs:** staff said Commercial v3.0 first, CE later. Release lag, not a stated permanent exclusion. [July 7](https://forum.plane.so/t/work-item-relation-tools-list-work-item-relation-definitions-list-work-item-relations-return-404-via-mcp-server-on-self-hosted-ce/274).
- **Private Wiki Collections:** an Enterprise self-hosted user also lacked them; staff said Cloud-only then, Commercial later. [June 16–17](https://forum.plane.so/t/cannot-create-private-collections-on-wiki/217).
- **Cycle filters in workspace Views:** staff confirmed unavailable and planned for Q3. [April 20](https://forum.plane.so/t/how-can-i-make-a-cycle-filter-in-workspace-view/103).
- **Cross-project cycles:** project-level currently; Teamspace cycles planned. [September 9](https://forum.plane.so/t/one-global-cycle/62).
- **Favoriting workspace-level Views:** missing star action logged as a request; saved Views and Favorites themselves exist in CE. [March 9](https://forum.plane.so/t/select-where-to-quick-link/44).
- **Custom-property sorting/grouping/columns:** also reported by Business/Airgapped users; Table columns planned first. [March 16](https://forum.plane.so/t/custom-properties-should-be-useable-for-sorting-grouping-and-view-columns/71).
- **Broader project-template coverage:** roadmap request. Work-item templates are project-level by design; forum does not establish CE template entitlement. [March 9](https://forum.plane.so/t/add-global-settings-for-all-project-at-workspace-level-or-add-to-project-template-all-possible-configurations/57), [February 26](https://forum.plane.so/t/add-workspace-related-templates-for-task-types-states-etc/38).
- **Burndown charts in completed-cycle analysis:** feature request. [June 11](https://forum.plane.so/t/burndown-chart-available-as-part-of-analysis-in-completed-cycles/209).

## Bugs or unclear entitlement

- **OAuth toggles disabling themselves:** staff could not reproduce some CE reports; treat as bugs/configuration reports, not a paywall. [March report](https://forum.plane.so/t/google-github-oauth-toggles-turn-off-automatically-in-plane-self-hosted/78), [May report](https://forum.plane.so/t/github-gitlab-and-google-oauth-login-methods-cannot-currently-be-enabled-in-the-self-hosted-community-edition-v1-3-0/140).
- **Labels in Views:** maintainer says filtering should work; reported as a bug. [July 3](https://forum.plane.so/t/you-cant-filter-by-labels-in-the-views/272).
- **API-created Views opening unfiltered:** writable/readable filter fields missing in API v1; maintainer acknowledged a bug. Report was Cloud, so CE applicability is unproven. [August 5](https://forum.plane.so/t/api-v1-cannot-set-last-used-filter-so-every-view-created-through-the-api-opens-unfiltered-in-the-ui/292).
- **Linear import project/module mapping:** confirmed by design; not CE-specific. [April 9](https://forum.plane.so/t/question-on-linear-import/87).
- **AI:** announced for self-hosted v2.4 with several model providers, but this forum post does not prove CE inclusion/exclusion. [March 5 announcement](https://forum.plane.so/t/plane-v2-4-0-plane-ai-now-available-for-self-hosted/53).
- **Governance, RBAC, SSO, integrations:** Commercial v3.0 advertises these, but that alone cannot prove each is missing from CE. [July 17 announcement](https://forum.plane.so/t/plane-commercial-v3-0-0-is-live-desktop-app-workspace-governance-rbac-and-more/281).

Potential follow-up candidates are relative-date filtering, workspace-view favorites, and cycle filtering. Each needs a local code audit and a separate scoped implementation decision; this scouting did not implement them.
