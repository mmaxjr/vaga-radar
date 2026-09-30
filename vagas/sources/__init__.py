from . import (companies, empregare, geekhunter, github, gupy, himalayas, infojobs, jobicy, linkedin, local, programathor,
               remoteok, remotive, vagascombr, weworkremotely, zohorecruit)

# nome -> função fetch(cfg) -> list[Job]
SOURCES = {
    "linkedin": linkedin.fetch,
    "gupy": gupy.fetch,
    "local": local.fetch,
    "infojobs": infojobs.fetch,
    "empregare": empregare.fetch,
    "companies": companies.fetch,
    "zohorecruit": zohorecruit.fetch,
    "jobicy": jobicy.fetch,
    "himalayas": himalayas.fetch,
    "geekhunter": geekhunter.fetch,
    "github": github.fetch,
    "programathor": programathor.fetch,
    "vagascombr": vagascombr.fetch,
    "remoteok": remoteok.fetch,
    "weworkremotely": weworkremotely.fetch,
    "remotive": remotive.fetch,
}
