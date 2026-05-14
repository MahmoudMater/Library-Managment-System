# Contributing

## Branching

- `main` — production-ready, protected; merge only via PR.
- `develop` — integration branch for the team.
- `feature/<github-username>/<short-topic>` — one topic per PR (e.g. `feature/alex/borrow-api`).

Flow: branch from `develop` → open PR into `develop` → when the milestone is done, PR `develop` → `main`.

## Commits

Use a short prefix so history is easy to read:

- `feat:` new feature
- `fix:` bug fix
- `test:` tests only
- `docs:` documentation
- `chore:` tooling, config, deps

Example: `feat: add borrow return endpoint with cache invalidation`

## Pull requests

- Keep PRs small and focused (one feature or fix).
- In the PR description, list what changed and how to test it.
- At least one other team member should review before merge (course policy may require this).

## Suggested ownership (for visible individual contributions)

| Area | Suggested owner |
|------|-----------------|
| Borrow/return service + tests | Member A |
| Users admin API + admin UI | Member B |
| Auth + books UI + public pages | Member C |
| Docker, Loki/Promtail, Grafana, README | Member D |

Replace with your real names in the root [README](README.md).
