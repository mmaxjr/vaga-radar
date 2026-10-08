from . import (companies, coodesh, empregare, geekhunter, github, gupy, himalayas, hn, infojobs, jobicy, linkedin, local, nerdin, programathor,
               remoteok, remotive, solides, torre, trampos, vagascombr, weworkremotely, zohorecruit)

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
    "nerdin": nerdin.fetch,
    "coodesh": coodesh.fetch,
    "trampos": trampos.fetch,
    "solides": solides.fetch,
    "torre": torre.fetch,
    "hn": hn.fetch,
    "github": github.fetch,
    "programathor": programathor.fetch,
    "vagascombr": vagascombr.fetch,
    "remoteok": remoteok.fetch,
    "weworkremotely": weworkremotely.fetch,
    "remotive": remotive.fetch,
}
