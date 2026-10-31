"""Small, clearly labelled sample catalog used until a data source is chosen."""

from skin_studio.domain.models import Hero

SAMPLE_HEROES = (
    Hero("sample-axe", "Axe"),
    Hero("sample-crystal-maiden", "Crystal Maiden"),
    Hero("sample-juggernaut", "Juggernaut"),
    Hero("sample-lina", "Lina"),
    Hero("sample-pudge", "Pudge"),
)


def search_heroes(query: str) -> tuple[Hero, ...]:
    normalized = query.strip().casefold()
    if not normalized:
        return SAMPLE_HEROES
    return tuple(hero for hero in SAMPLE_HEROES if normalized in hero.name.casefold())
