"""S
QLAlchemy модель метаданных КА (название, NORAD ID и т.д.)
"""

from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Satellite(Base):
    __tablename__ = "satellites"

    id: Mapped[int] = mapped_column(primary_key=True)
    norad_id: Mapped[int] = mapped_column(unique=True, index=True)
    name: Mapped[str | None]
    international_designator: Mapped[str | None]
    classification: Mapped[str | None]
