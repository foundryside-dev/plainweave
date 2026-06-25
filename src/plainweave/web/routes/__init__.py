from __future__ import annotations

from starlette.applications import Starlette


def register_all(app: Starlette) -> None:
    # Each route module appends its routes; populated as tasks land.
    from plainweave.web.routes import goals, intent, requirements, review

    requirements.register(app)
    intent.register(app)
    review.register(app)
    goals.register(app)
