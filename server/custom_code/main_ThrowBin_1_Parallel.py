"""Retired experiment driver; see docs/MIGRATION.md for parameter mapping."""

if __name__ == "__main__":
    raise SystemExit(
        "This driver has moved to the shared runner. From the repository root run:\n"
        "bincovering run --config-dir configs --config-name throwbin\n"
        "Pass parameters explicitly; historical defaults and RNG streams are documented in docs/MIGRATION.md."
    )
