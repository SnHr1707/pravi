from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from .config import DATABASE_URL

_kwargs = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    _kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_kwargs)


def _add_missing_columns() -> None:
    """Tiny migration: databases created by an older version get the new (nullable) columns added,
    so an existing Neon database keeps working after an upgrade."""
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    for table in SQLModel.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        have = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name in have:
                continue
            ctype = col.type.compile(dialect=engine.dialect)
            default = ""
            if col.default is not None and getattr(col.default, "is_scalar", False):
                v = col.default.arg
                default = " DEFAULT " + (("TRUE" if v else "FALSE") if isinstance(v, bool)
                                         else str(v) if isinstance(v, (int, float)) else "'" + str(v).replace("'", "''") + "'")
            try:
                with engine.begin() as conn:
                    conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ctype}{default}'))
                print(f"[db] added column {table.name}.{col.name}")
            except Exception as e:  # another server instance added it at the same moment
                print(f"[db] could not add {table.name}.{col.name}: {type(e).__name__}")


def init_db(reset: bool = False) -> None:
    from . import models  # noqa: F401  (register tables)
    if reset:
        SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    if not reset:
        _add_missing_columns()


def get_session():
    with Session(engine) as session:
        yield session
