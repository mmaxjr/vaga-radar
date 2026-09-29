from . import github, gupy, linkedin, programathor, remoteok, remotive, vagascombr, weworkremotely

# nome -> função fetch(cfg) -> list[Job]
SOURCES = {
    "linkedin": linkedin.fetch,
    "gupy": gupy.fetch,
    "github": github.fetch,
    "programathor": programathor.fetch,
    "vagascombr": vagascombr.fetch,
    "remoteok": remoteok.fetch,
    "weworkremotely": weworkremotely.fetch,
    "remotive": remotive.fetch,
}
