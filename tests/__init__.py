"""TOOL · the suite, mirroring the package layout it tests.

Five directories, in the order they are written (spec.md § *Testing Strategy*): ``guards/`` the
architectural rules, before any service exists; ``stages/`` one module per stage; ``properties/``
the bus and conservation properties over a whole corpus; ``shells/`` HTTP and in-process compared;
``integration/`` the live panel, a real store, a declared corpus, all behind ``-m integration``.
"""
