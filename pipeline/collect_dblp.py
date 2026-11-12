"""Collect the eight approved DBLP streams, retaining overlapping memberships."""
import json,re
from urllib.parse import urlencode,unquote
from cg_config import DATA,VENUES,YEAR
from network import fetch,retrieved,save
PREFIX='PREFIX d: <https://dblp.org/rdf/schema#> '
def query(q):
    url='https://sparql.dblp.org/sparql?'+urlencode({'query':PREFIX+q,'format':'json'})
    return fetch(url)['results']['bindings'],url

def main():
    records={};ledger=[]
    for venue,meta in VENUES.items():
        condition='FILTER(?label IN ('+','.join(json.dumps(x) for x in meta['labels'])+'))' if 'labels' in meta else ''
        base=f'?p d:publishedInStream <https://dblp.org/streams/{meta["stream"]}>; d:title ?title; d:yearOfPublication ?year; d:publishedIn ?label; d:authoredBy ?author . FILTER(STR(?year) <= "{YEAR}") {condition}'
        counts,counturl=query('SELECT (COUNT(DISTINCT ?p) AS ?n) WHERE {'+base+'}')
        expected=int(counts[0]['n']['value']);rows={};offset=0;urls=[]
        while len(rows)<expected:
            q="""SELECT ?p ?title ?year ?label
              (GROUP_CONCAT(DISTINCT STR(?doi);separator="|") AS ?dois)
              (GROUP_CONCAT(DISTINCT CONCAT(STR(?ordinal),"~",STR(?creator),"~",?name);separator="|") AS ?authors)
              (GROUP_CONCAT(DISTINCT STR(?toc);separator="|") AS ?tocs)
              (SAMPLE(?volume) AS ?vol) (SAMPLE(?issue) AS ?iss) (SAMPLE(?pages) AS ?page)
              WHERE {"""+base+"""
                ?p d:hasSignature ?sig . ?sig a d:AuthorSignature; d:signatureCreator ?creator; d:signatureDblpName ?name; d:signatureOrdinal ?ordinal .
                OPTIONAL {?p d:doi ?doi} OPTIONAL {?p d:listedOnTocPage ?toc}
                OPTIONAL {?p d:publishedInJournalVolume ?volume} OPTIONAL {?p d:publishedInJournalVolumeIssue ?issue} OPTIONAL {?p d:pagination ?pages}
              } GROUP BY ?p ?title ?year ?label ORDER BY ?p LIMIT 3000 OFFSET """+str(offset)
            results,url=query(q);urls.append({'url':url,'retrieved_at':retrieved(url),'rows':len(results)})
            if not results: break
            for b in results:
                v=lambda k:b.get(k,{}).get('value','')
                key=v('p');authors=sorted([a.split('~',2) for a in v('authors').split('|')],key=lambda a:int(a[0]))
                dois=sorted({re.sub(r'\s+','',unquote(d).lower().removeprefix('https://doi.org/').removeprefix('http://doi.org/')) for d in v('dois').split('|') if d})
                row={'dblp_key':key.removeprefix('https://dblp.org/rec/'),'title':v('title').rstrip('.'),'publication_year':int(v('year')),'container':v('label'),
                     'authors':[re.sub(r'\s+\d{4}$','',a[2]) for a in authors],'author_ids':[a[1] for a in authors],
                     'doi':dois[0] if dois else '', 'doi_aliases':dois,'tocs':v('tocs').split('|'),'volume':v('vol'),'issue':v('iss'),'pages':v('page'),'source_url':key}
                rows[key]=row
                if key not in records: records[key]={**row,'venues':[]}
                if venue not in records[key]['venues']: records[key]['venues'].append(venue)
            offset+=len(results)
            print(f'DBLP {venue}: {len(rows)}/{expected}',flush=True)
        if len(rows)!=expected: raise RuntimeError(f'Incomplete DBLP {venue}: {len(rows)}/{expected}')
        ledger.append({'venue':venue,'stream':meta['stream'],'expected':expected,'retrieved':len(rows),'count_url':counturl,'pages':urls,'complete':True})
        save(DATA/'dblp.json',list(records.values()));save(DATA/'coverage_dblp.json',ledger)
if __name__=='__main__': main()
