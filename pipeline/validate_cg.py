"""Check publication identities, overlapping membership totals and geographic statistics."""
import csv,gzip,json,re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit,unquote
from bs4 import BeautifulSoup
from cg_config import DATA,ROOT,VENUES,YEAR
from metadata import EXCLUDED_TOC,normalize_doi,edition
from taxonomy import classify

def load(name):return json.loads((DATA/(name+'.json')).read_text(encoding='utf-8'))
def main():
    papers=load('papers');s=load('summary');g=load('geography');ledger=load('coverage')
    assert set(s['venues'])==set(VENUES)
    assert len(papers)==s['total']==len({p['id'] for p in papers})
    dois=[d for p in papers for d in p['doi_aliases']]
    assert len(dois)==len(set(dois)), 'DOI aliases appear in multiple publications'
    for p in papers:
        assert set(p['venues'])<=set(VENUES) and p['venue'] in p['venues']
        assert set(p['venue_years'])==set(p['venues'])
        assert p['year']==p['venue_years'][p['venue']]
        assert 1900<=p['publication_year']<=YEAR
        assert p['doi']==normalize_doi(p['doi'])
        assert p['title'] and p['authors']
        assert not set(p.get('tocs',[]))&set(EXCLUDED_TOC)
        assert (p['topics'],p['subtopics'])==classify(p['title'])
        for v in p['venues']:
            assert VENUES[v]['since']<=p['venue_years'][v]<=YEAR,(p['title'],v,p['venue_years'][v])
            if VENUES[v]['kind']=='conference' and 'DBLP' in p['sources']:
                assert p['venue_years'][v]==edition(p,v)[0]
        if p['citation_count'] is not None:assert p['citation_source']=='OpenAlex' and p['citation_updated'] and p['citation_count']>=0
    assert s['with_multiple_venues']==sum(len(p['venues'])>1 for p in papers)
    assert {int(y):n for y,n in s['unique_years'].items()}==dict(Counter(p['year'] for p in papers))
    for v in VENUES:
        rows=[p for p in papers if v in p['venues']];m=s['venues'][v]
        assert len(rows)==m['count']
        assert dict(Counter(p['venue_years'][v] for p in rows))=={int(y):n for y,n in m['years'].items()}
    assert len(ledger['dblp'])==8 and len(ledger['crossref'])==4
    for r in ledger['dblp']+ledger['crossref']:assert r['complete'] and r['expected']==r['retrieved']
    assert ledger['openalex']['complete'] and not ledger['openalex']['errors']
    assert g['collection_complete'] and load('coverage_affiliations')['complete']
    assert set(g['papers'])<={p['id'] for p in papers}
    known=set();mapped=0;returned=0;located=0
    for entry in g['papers'].values():
        if entry['countries']:mapped+=1
        assert entry['known_authors']<=entry['authors']
        returned+=entry['authors'];located+=entry['known_authors']
        local=set()
        for country,ids in entry['countries'].items():
            assert re.fullmatch('[A-Z]{2}',country)
            assert len(ids)==len(set(ids)) and all(re.fullmatch('A[0-9]+',a) for a in ids)
            known.update(ids);local.update(ids)
        assert len(local)==entry['known_authors']
    c=g['coverage'];assert c['total_papers']==len(papers) and c['matched_papers']==len(g['papers'])
    assert c['papers_with_country']==mapped and c['unique_author_ids_with_country']==len(known)
    assert c['returned_authorships']==returned and c['authorships_with_country']==located
    with gzip.open(ROOT/'downloads/cgpaper_atlas.csv.gz','rt',encoding='utf-8-sig',newline='') as f:
        exported=list(csv.DictReader(f));assert len(exported)==len(papers)
        assert {p['id'] for p in exported}=={p['id'] for p in papers}
    for path in ROOT.glob('*.html'):
        soup=BeautifulSoup(path.read_text(encoding='utf-8'),'lxml')
        assert 'CG Paper Atlas' in soup.title.text
        for tag in soup.select('[href],[src]'):
            ref=tag.get('href') or tag.get('src');url=urlsplit(ref)
            if not url.scheme and url.path:assert (ROOT/unquote(url.path)).exists(),ref
        assert len({e['id'] for e in soup.select('[id]')})==len(soup.select('[id]'))
    for path in [*DATA.glob('*.json'),*(ROOT/'downloads').glob('*')]:assert path.stat().st_size<100*1024*1024,path
    print(f'PASS: {len(papers):,} unique CG publications; 8 overlapping venue memberships, editions, source ledgers, geography and exports agree.')
if __name__=='__main__':main()
