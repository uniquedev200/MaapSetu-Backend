"""Generic, reusable repository base."""

from typing import Any, Dict, Generic, List, Optional, Sequence, Type, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Thin CRUD wrapper around a SQLAlchemy session for a single model."""

    model: Type[ModelT]

    def __init__(self, db: Session):
        self.db = db

    # -- Create ----------------------------------------------------------
    def add(self, obj: ModelT, *, commit: bool = True, flush: bool = False) -> ModelT:
        self.db.add(obj)
        if flush:
            self.db.flush()
        if commit:
            self.db.commit()
            self.db.refresh(obj)
        return obj

    def create(self, **kwargs: Any) -> ModelT:
        obj = self.model(**kwargs)
        return self.add(obj)

    # -- Read ------------------------------------------------------------
    def get(self, id: int) -> Optional[ModelT]:
        return self.db.get(self.model, id)

    def get_or_404(self, id: int, resource: Optional[str] = None) -> ModelT:
        obj = self.get(id)
        if obj is None:
            resource = resource or self.model.__name__
            raise NotFoundError(resource)
        return obj

    def get_by(self, resource: str = "Resource", **filters: Any) -> Optional[ModelT]:
        stmt = select(self.model).filter_by(**filters)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_or_404(self, resource: str, **filters: Any) -> ModelT:
        obj = self.get_by(**filters)
        if obj is None:
            raise NotFoundError(resource)
        return obj

    def all(self) -> List[ModelT]:
        return list(self.db.execute(select(self.model)).scalars().all())

    def count(self, *whereclauses: Any) -> int:
        stmt = select(func.count()).select_from(self.model)
        if whereclauses:
            stmt = stmt.where(*whereclauses)
        return int(self.db.execute(stmt).scalar_one())

    def query(self, *whereclauses: Any) -> Sequence[ModelT]:
        stmt = select(self.model).where(*whereclauses) if whereclauses else select(self.model)
        return self.db.execute(stmt).scalars().all()

    # -- Update / delete -------------------------------------------------
    def update(self, obj: ModelT, **fields: Any) -> ModelT:
        for key, value in fields.items():
            setattr(obj, key, value)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def save(self, obj: ModelT, *, commit: bool = True) -> ModelT:
        self.db.add(obj)
        if commit:
            self.db.commit()
            self.db.refresh(obj)
        return obj

    def delete(self, obj: ModelT, *, commit: bool = True) -> None:
        self.db.delete(obj)
        if commit:
            self.db.commit()