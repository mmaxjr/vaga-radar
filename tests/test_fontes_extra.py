from vagas.sources import companies, hn, torre

CARD = ('<a href="https://torre.ai/post/{id}-{slug}?utm_source=x" class="grid-cols-job"><div class="hex-avatar text-h2"></div>'
        '<div class="text-accent text-h2 pt-8">{titulo}</div>'
        '<span class="text-accent text-regular cursor-pointer">{empresa}</span><span>{onde}</span></a>')


def test_torre_so_cartoes_remotos_com_titulo_e_empresa():
    html = (CARD.format(id="AAA", slug="qa-full-stack", titulo="QA Full Stack", empresa="Makers", onde="Remote")
            + CARD.format(id="BBB", slug="loja", titulo="Vendedor", empresa="Loja", onde="Bogotá, Colombia"))
    jobs = torre.parse(html)
    assert [(j.title, j.company, j.url) for j in jobs] == [("QA Full Stack", "Makers", "https://torre.ai/post/AAA-qa-full-stack")]
    assert jobs[0].source == "torre" and jobs[0].international and "latam" in jobs[0].location.lower()


def comentario(i, texto):
    return {"id": i, "text": texto, "created_at": "2026-10-01T10:00:00Z"}


def test_hn_so_anuncios_remotos_abertos_ao_mundo_ou_latam():
    kids = [
        comentario(1, "Acme | Senior DevOps Engineer | Remote (Worldwide) | Full-time<p>Detalhes longos aqui."),
        comentario(2, "Beta | Backend | NYC ONSITE | Full-time<p>We are remote friendly in the body."),
        comentario(3, "Gama | SRE | Remote (US only) | Full-time"),
        comentario(4, "Delta | Python Dev | REMOTE - Brazil, LATAM | Contract"),
        {"id": 5, "text": None},
    ]
    jobs = hn.parse(kids)
    assert [j.url for j in jobs] == ["https://news.ycombinator.com/item?id=1", "https://news.ycombinator.com/item?id=4"]
    assert jobs[0].company == "Acme" and jobs[0].title.startswith("Acme | Senior DevOps") and jobs[0].source == "hn"


def test_ashby_so_remotas_e_any_location_vira_anywhere():
    itens = [
        {"title": "SRE", "location": "Any Location", "isRemote": True, "workplaceType": "Remote", "team": "Infra",
         "employmentType": "FullTime", "jobUrl": "https://jobs.ashbyhq.com/x/1"},
        {"title": "Office Manager", "location": "Madrid", "isRemote": False, "workplaceType": "OnSite", "jobUrl": "https://jobs.ashbyhq.com/x/2"},
        {"title": "Backend", "location": "The Americas", "isRemote": True, "isListed": False, "jobUrl": "https://jobs.ashbyhq.com/x/3"},
    ]
    jobs = companies.parse_ashby("acme-co", itens)
    assert [(j.title, j.location, j.company) for j in jobs] == [("SRE", "Anywhere", "Acme Co")]
    assert jobs[0].international and jobs[0].tags == ["Infra", "FullTime"]
