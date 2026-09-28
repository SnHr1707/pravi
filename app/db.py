from sqlmodel import Session, SQLModel, create_engine

from .config import DATABASE_URL

_kwargs = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    _kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **_kwargs)


def init_db(reset: bool = False) -> None:
    from . import models  # noqa: F401  (register tables)
    if reset:
        SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
