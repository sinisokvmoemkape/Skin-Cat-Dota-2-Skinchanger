# Contributing

Contributions are welcome for the independent, cross-platform organizer and its documentation.

1. Open an issue describing the user need or bug before large changes.
2. Keep UI, domain logic, storage, and platform behavior in their documented layers.
3. Do not add Valve game assets or proprietary third-party material without a documented redistribution license.
4. Keep Steam discovery read-only. Do not add game-process access, injection, anti-cheat interference, hidden-information extraction, or network circumvention.
5. Add or update tests and Russian/English Qt translations for user-visible behavior.
6. Run `python scripts/compile_translations.py`, `ruff check .`, and `pytest` before opening a pull request.

Pull requests should explain the behavior change, platform impact, safety boundary, and exact verification commands/results. Keep changes focused and preserve unrelated user work.
