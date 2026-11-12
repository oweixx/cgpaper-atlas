"""Audit complete Crossref journal-article inventories for the four approved ISSNs."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode
from bs4 import BeautifulSoup
import re
from cg_config import DATA, VENUES, YEAR
from network import fetch, retrieved, save

def clean(text):
    return re.sub(r'\s+', ' ', BeautifulSoup(str(text or ''), 'lxml').get_text(' ', strip=True)).strip()

def collect(venue, meta):
    params = {'rows':1000,'cursor':'*','filter':'type:journal-article',
              'select':'DOI,title,author,published,published-print,published-online,issued,type,container-title,abstract,volume,issue,page'}
    if venue in ['CGF','TVCG']:
        # These inventories fit Crossref's 10k offset window. Publication sorting
        # is explicitly unsupported with cursors; use stable dated pages here.
        params.pop('cursor')
        params.update(rows=500,sort='published',order='asc',offset=0)
    records, seen, pages = [], set(), []
    total = None
    while True:
        url = f'https://api.crossref.org/journals/{meta["issn"]}/works?' + urlencode(params)
        msg = fetch(url)['message']
        if total is None: total = msg['total-results']
        items = msg.get('items', [])
        pages.append({'url':url,'retrieved_at':retrieved(url),'rows':len(items)})
        for w in items:
            doi = w['DOI'].lower()
            if doi in seen: continue
            seen.add(doi)
            dates = {k:w[k].get('date-parts',[[]])[0] for k in ['published-print','published','published-online','issued'] if w.get(k)}
            year = next((d[0] for d in dates.values() if d), 0)
            authors = [clean(' '.join(filter(None,[a.get('given'),a.get('family')])) or a.get('name','')) for a in w.get('author',[])]
            title = clean((w.get('title') or [''])[0])
            records.append({'doi':doi,'title':title,'authors':authors,'publication_year':year,'dates':dates,
                            'venues':[venue],'container':(w.get('container-title') or [''])[0],
                            'abstract':clean(w.get('abstract')),'volume':w.get('volume',''),'issue':w.get('issue',''),
                            'pages':w.get('page',''),'source_url':'https://api.crossref.org/works/'+doi})
        print(f'Crossref {venue}: {len(seen)}/{total}',flush=True)
        if len(seen) >= total: break
        if 'offset' in params:
            if not items or params['offset']+len(items)>=10000:raise RuntimeError(f'Incomplete Crossref {venue}')
            params['offset']+=len(items)
            continue
        nxt = msg.get('next-cursor')
        if not items or not nxt or nxt == params['cursor']: raise RuntimeError(f'Incomplete Crossref {venue}')
        params['cursor'] = nxt
    if len(seen) != total: raise RuntimeError(f'Crossref total changed for {venue}; refresh collection')
    return records, {'venue':venue,'issn':meta['issn'],'expected':total,'retrieved':len(seen),'complete':True,'pages':pages}

def main():
    rows, reports, errors = [], [], []
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = [pool.submit(collect,v,m) for v,m in VENUES.items() if m['kind']=='journal']
        for job in as_completed(jobs):
            try:
                data, report = job.result(); rows.extend(data); reports.append(report)
            except Exception as exc:
                errors.append(str(exc));print('Crossref collection error:',str(exc),flush=True)
            save(DATA/'crossref.json',rows);save(DATA/'coverage_crossref.json',reports)
    if errors:raise RuntimeError(errors)
if __name__ == '__main__': main()
