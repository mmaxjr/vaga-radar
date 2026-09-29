from . import geekhunter, github, gupy, linkedin, local, programathor, remoteok, remotive, vagascombr, weworkremotely

# nome -> função fetch(cfg) -> list[Job]
SOURCES = {
    "linkedin": linkedin.fetch,
    "gupy": gupy.fetch,
    "local": local.fetch,
    "geekhunter": geekhunter.fetch,
    "github": github.fetch,
    "programathor": programathor.fetch,
    "vagascombr": vagascombr.fetch,
    "remoteok": remoteok.fetch,
    "weworkremotely": weworkremotely.fetch,
    "remotive": remotive.fetch,
}
