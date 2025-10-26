"""
Database package initialization.
"""

from app.database.mongodb import database, MongoDB

__all__ = ['database', 'MongoDB']
