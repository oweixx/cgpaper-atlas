"""Exact DOI enrichment: citations, abstracts, open PDF links and work-time affiliations."""
import os,re
from urllib.parse import urlencode,urlsplit,parse_qs
from concurrent.futures import ThreadPoolExecutor
from cg_config import DATA
from network import fetch,retrieved,save
from metadata import normalize_doi
import json

def normalize_authorships(work):
    authors={}
    for a in work.get('authorships',[]):
        ident=(a.get('author') or {}).get('id','')
        if not ident:continue
        countries=set(a.get('countries') or [])
        countries.update(i.get('country_code') for i in a.get('institutions',[]) if i.get('country_code'))
        authors.setdefault(ident.rsplit('/',1)[-1],set()).update(c for c in countries if re.fullmatch('[A-Z]{2}',c or ''))
    return [{'id':k,'countries':sorted(v)} for k,v in sorted(authors.items())]

def batch(dois):
    url='https://api.openalex.org/works?'+urlencode({'filter':'doi:'+'|'.join(dois),'per-page':100,'select':'id,doi,title,cited_by_count,abstract_inverted_index,authorships,best_oa_location'})
    headers={'Authorization':'Bearer '+os.environ['OPENALEX_API_KEY']} if os.environ.get('OPENALEX_API_KEY') else {}
    data=fetch(url,headers=headers);date=retrieved(url);allowed=set(dois);enriched={};affiliations={};rejected=[]
    for w in data['results']:
        doi=normalize_doi(w.get('doi'))
        if doi not in allowed:rejected.append({'id':w['id'],'doi':doi});continue
        index=w.get('abstract_inverted_index') or {}
        abstract=' '.join(word for _,word in sorted((i,word) for word,positions in index.items() for i in positions))
        enriched[doi]={'openalex_id':w['id'],'title':w.get('title'),'abstract':abstract,'citation_count':w.get('cited_by_count'),
                       'citation_source':'OpenAlex','citation_updated':date,'pdf_url':(w.get('best_oa_location') or {}).get('pdf_url') or ''}
        affiliations[doi]={'openalex_id':w['id'],'authors':normalize_authorships(w),'returned_authorships':len(w.get('authorships',[])),
                           'possibly_truncated':len(w.get('authorships',[]))>=100,'retrieved_at':date}
    return enriched,affiliations,{'url':url,'requested':len(dois),'matched':len(enriched),'rejected_doi_mismatches':rejected,'retrieved_at':date}

def main():
    rows=json.loads((DATA/'papers.json').read_text(encoding='utf-8'))
    dois=sorted({p['doi'] for p in rows if p['doi']})
    def existing(name,default):
        path=DATA/(name+'.json')
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
    enriched=existing('enrichment',{});affiliations=existing('affiliations',{});reports=existing('coverage_enrichment',{}).get('batches',[]);errors=[]
    covered={d for r in reports for d in parse_qs(urlsplit(r['url']).query)['filter'][0].removeprefix('doi:').split('|')}
    pending=sorted(set(dois)-covered);groups=[pending[i:i+100] for i in range(0,len(pending),100)]
    total_batches=len(reports)+len(groups)
    if not groups:
        print('All current corpus DOIs already queried; normalized snapshot retained.',flush=True);return
    with ThreadPoolExecutor(max_workers=3) as pool:
        for start in range(0,len(groups),3):
            jobs=[pool.submit(batch,g) for g in groups[start:start+3]]
            for i,job in enumerate(jobs):
                try:
                    e,a,r=job.result();enriched.update(e);affiliations.update(a);reports.append(r)
                except Exception as exc:errors.append({'batch':start+i,'error':str(exc)})
            if start%30==0 or errors or start+3>=len(groups):
                ledger={'requested_dois':len(covered|set(dois)),'corpus_dois':len(dois),'matched_dois':len(enriched),'complete':len(reports)==total_batches and not errors,'total_batches':total_batches,'processed_batches':len(reports),'batches':reports,'errors':errors}
                save(DATA/'enrichment.json',enriched);save(DATA/'affiliations.json',affiliations)
                save(DATA/'coverage_enrichment.json',ledger);save(DATA/'coverage_affiliations.json',ledger)
                print(f'OpenAlex {len(reports)}/{total_batches} batches; {len(enriched)} exact matches; errors={len(errors)}',flush=True)
            if errors:raise RuntimeError(errors)
if __name__=='__main__':main()
