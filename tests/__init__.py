"""TOOL · the suite, mirroring the package layout it tests.

Three directories, in the order they are written (`spec.md` § *Testing Strategy*): ``guards/`` the
architectural rules, which hold before any service exists; ``profile/`` the task's own logic --
the scan, the panel, and how a model's config is read; ``edge/`` each route through ``TestClient``,
driven by its own arguments and reaching no provider.

Nothing here needs the network. ``-m integration`` is declared in ``pyproject.toml`` for a test
that would, and no test carries the marker yet.
"""
