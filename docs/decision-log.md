# Decision Log

## 2026-03-18

### Decision
Use a Python-first modular monolith for version 1.

### Reason
It keeps the system small enough for a beginner to understand while still teaching ingestion, persistence, profiling, rules, testing, and UI development.

### Tradeoff
The frontend is less flexible than a separate React application, but the learning curve is much lower.

## 2026-03-18

### Decision
Store raw uploads on disk and metadata, profiles, rules, and issues in DuckDB.

### Reason
That preserves the original file, keeps the architecture local-first, and avoids introducing separate storage systems too early.

### Tradeoff
This is not the right long-term design for a multi-user hosted application.

## 2026-03-18

### Decision
Start with built-in rule heuristics instead of user-authored rules.

### Reason
It keeps the first version focused on the core learning loop: upload, inspect, detect, explain, and export.

### Tradeoff
Users cannot customize validations yet, so some domain-specific rules must wait for version 2.

