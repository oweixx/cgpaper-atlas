"""Check publication identities, overlapping membership totals and geographic statistics."""
import csv,gzip,json,re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit,unquote
from bs4 import BeautifulSoup
from cg_config import DATA,ROOT,VENUES,YEAR
from metadata import EXCLUDED_TOC,normalize_doi,edition
from taxonomy import classify_with_evidence,VERSION,normalize

def load(name):return json.loads((DATA/(name+'.json')).read_text(encoding='utf-8'))
def main():
    papers=load('papers');s=load('summary');g=load('geography');ledger=load('coverage')
    topic_metadata=load('topic_metadata')
    assert load('coverage_topics')['complete']
    assert set(s['venues'])==set(VENUES)
    assert len(papers)==s['total']==len({p['id'] for p in papers})
    dois=[d for p in papers for d in p['doi_aliases']]
    topic_evidence={}
    for path in (DATA/'topic_evidence').glob('*.json'):topic_evidence.update(json.loads(path.read_text(encoding='utf-8')))
    assert set(topic_evidence)=={p['id'] for p in papers}
    assert len(dois)==len(set(dois)), 'DOI aliases appear in multiple publications'
    for p in papers:
        assert set(p['venues'])<=set(VENUES) and p['venue'] in p['venues']
        assert set(p['venue_years'])==set(p['venues'])
        assert p['year']==p['venue_years'][p['venue']]
        assert 1900<=p['publication_year']<=YEAR
        assert p['doi']==normalize_doi(p['doi'])
        assert p['title'] and p['authors']
        assert not set(p.get('tocs',[]))&set(EXCLUDED_TOC)
        classification=classify_with_evidence(p['title'],p['abstract'],topic_metadata.get(p['doi']))
        assert (p['topics'],p['subtopics'])==(classification.pop('topics'),classification.pop('subtopics'))
        assert p['classification_version']==VERSION and p['classification_basis']==classification['basis']
        assert topic_evidence[p['id']]==classification
        for e in classification['evidence']:
            assert e['area'] in p['topics'] and e['subtopic'] in p['subtopics']
            if e['basis']=='openalex_keyword':
                assert any(k['id']==e['source_url'] and k['score']==e['source_score'] and k['display_name']==e['terms'][0] for k in topic_metadata[p['doi']]['keywords'])
            else:
                source=normalize(p[e['basis']])
                if e['basis']=='abstract':
                    source=re.sub(r'\be\.g\.', 'for example', source)
                    source=re.sub(r'\bi\.e\.', 'that is', source)
                assert all(term in source for term in e['terms']),p['id']
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
        lookup={p['id']:p for p in papers}
        for row in exported:
            p=lookup[row['id']]
            for key in ['topics','subtopics']:assert row[key]=='; '.join(p[key])
            assert row['classification_version']==VERSION and row['classification_basis']==p['classification_basis']
    template=(ROOT/'pipeline/site.html').read_text(encoding='utf-8').replace('<!-- ANALYTICS -->',(ROOT/'pipeline/analytics.html').read_text(encoding='utf-8'))
    for path in ROOT.glob('*.html'):
        assert path.read_text(encoding='utf-8')==template, 'Generated page differs from its template: '+path.name
        soup=BeautifulSoup(path.read_text(encoding='utf-8'),'lxml')
        assert 'CG Paper Atlas' in soup.title.text
        for tag in soup.select('[href],[src]'):
            ref=tag.get('href') or tag.get('src');url=urlsplit(ref)
            if not url.scheme and url.path:assert (ROOT/unquote(url.path)).exists(),ref
        assert len({e['id'] for e in soup.select('[id]')})==len(soup.select('[id]'))
    assert s['classification']['version']==VERSION
    assert s['classification']['unclassified']==sum(p['topics']==['Other / Unclassified'] for p in papers)
    audit=load('topic_classification_audit')
    assert audit['basis_counts']==dict(Counter(p['classification_basis'] for p in papers))==s['classification']['basis_counts']
    assert audit['area_counts']==dict(Counter(t for p in papers for t in p['topics']))
    from evaluate_topics import evaluate
    assert load('topic_validation')==evaluate(papers,load('topic_reference_holdout')), 'Evaluation report is stale'
    assert load('topic_reference_holdout')['classifier_sha256_before_sampling']==load('topic_validation')['classifier_sha256'], 'Classifier changed after the held-out reference was frozen'
    for path in [*DATA.rglob('*.json'),*(ROOT/'downloads').glob('*')]:assert path.stat().st_size<100*1024*1024,path
    print(f'PASS: {len(papers):,} unique CG publications; 8 overlapping venue memberships, editions, source ledgers, geography and exports agree.')
if __name__=='__main__':main()
