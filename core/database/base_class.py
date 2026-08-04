"""
base_class.py — Common base for every persisted model.

Aliases ODMantic's :class:`odmantic.Model` under a project-owned name so the ODM
dependency is referenced in one place. Should the persistence layer ever change,
this alias is the seam to edit rather than every model module.

Usage:
    >>> from core.database.base_class import Base
    >>>
    >>> class Product(Base):
    ...     name: str
    ...     price: float

Note:
    Subclassing :class:`Base` is what maps a class to a MongoDB collection.
    ODMantic derives the collection name from the class name, supplies the
    ``id`` primary key, and validates every document on write.
"""

from odmantic import Model

#: Base class for all persisted models in this project.
Base = Model
