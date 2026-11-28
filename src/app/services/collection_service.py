"""CollectionService (Design Figure 3) - personal collections (FR-15, UC-14).

Implemented now: ensure_favorites(), which AuthService.register_user() calls (Figure 3).
Still to add for FR-15: create(), rename(), delete(), add_prompt(), remove_prompt().
"""
from ..models import FAVORITES_NAME, Collection


class CollectionService:
    @staticmethod
    def ensure_favorites(user):
        """Give the user their fixed Favorites collection if they do not have one yet.

        Does not commit: the caller's transaction saves it together with the user.
        """
        for collection in user.collections:
            if collection.is_default:
                return collection
        favorites = Collection(name=FAVORITES_NAME, is_default=True)
        user.collections.append(favorites)
        return favorites
