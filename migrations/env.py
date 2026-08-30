"""TOOL · Alembic's entry point: the schema it compares against, and the DSN it applies to.

Outside `src/`, because it is not part of the package that ships -- it is the tool that moves a
database from one version of the package's schema to the next. It imports `edge/store/`, which is
the right direction: a migration is I/O about the edge's own tables.

The DSN comes from `edge/store/session.py` and never from `alembic.ini`, so `alembic upgrade head`
and a running process address the same database by the same rule (§35, §36).
"""

from alembic import context

from dataforce.edge.store.models import Base
from dataforce.edge.store.session import store_engine, store_url

# What autogenerate compares a live database against. `Base` holds the three tables and no others.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit the SQL without connecting, which is how a migration is reviewed before it is run."""
    context.configure(
        url=store_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply the migrations against the attached database, in one transaction."""
    with store_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
