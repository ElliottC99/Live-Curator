# Compound Solutions Knowledge Base (`docs/solutions/`)

## Purpose
Persistent repository of solved engineering problems and verified architectural patterns. Ensures solutions compound so future agents and developers never re-investigate resolved issues.

## Key Components
- **`schema.yaml`**: Formal validation schema for solution frontmatter (problem types, severity, components, and root causes).
- **`patterns/`**: Project-wide critical patterns registry (`critical-patterns.md`) and modular pattern files.
- **`integration_issue/`**: Ingestion, third-party API, and web scraping solution documents.
- **`templates/`**: Standardized templates for new solution documents.

## Component Details
- `schema.yaml`: Enforces strict enum values for machine-readable compounding metadata.
- `patterns/critical-patterns.md`: Index of mandatory engineering patterns.
- `integration_issue/live-curator-engine-architecture.md`: Reference architecture for DICE, Spotify, and UK review ingestion.
- `integration_issue/pricing-soldout-persistence-and-club-taste-tagging-20261103.md`: Solution for SQLite schema migration, ticket prices, and club night taste tagging.

## Changelog
### 2026-11-03
- Documented solution for ticket pricing, sold-out persistence, and club night taste tagging.
- Maintained pattern registry continuity across 32 patterns.
