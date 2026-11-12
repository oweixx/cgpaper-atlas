"""Snapshot OpenAlex aboutness by exact DOI; credentials only in headers."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode
from cg_config import DATA
from network import fetch,retrieved,save
from metadata import normalize_doi

def batch(dois):
    url='https://api.openalex.org/works?'+urlencode({'filter':'doi:'+'|'.join(dois),'per-page':100,'select':'id,doi,primary_topic,topics,keywords'})
    headers={'Authorization':'Bearer '+os.environ['OPENALEX_API_KEY']} if os.environ.get('OPENALEX_API_KEY') else {}
    data=fetch(url,headers=headers);allowed=set(dois);rows={}
    for work in data['results']:
        doi=normalize_doi(work.get('doi'))
        if doi not in allowed:continue
        slim=lambda t:{k:t[k] for k in ['id','display_name','score'] if k in t}
        rows[doi]={'openalex_id':work['id'],'primary_topic':slim(work.get('primary_topic') or {}),
                   'topics':[slim(t) for t in work.get('topics',[])],
                   'keywords':[slim(k) for k in work.get('keywords',[])], 'retrieved_at':retrieved(url)}
    return rows,{'url':url,'requested_dois':dois,'matched':len(rows),'retrieved_at':retrieved(url)}

def main():
    papers=json.loads((DATA/'papers.json').read_text(encoding='utf-8'))
    dois=sorted({p['doi'] for p in papers if p['doi']})
    rows=json.loads((DATA/'topic_metadata.json').read_text(encoding='utf-8')) if (DATA/'topic_metadata.json').exists() else {}
    ledger=json.loads((DATA/'coverage_topics.json').read_text(encoding='utf-8')) if (DATA/'coverage_topics.json').exists() else {}
    reports=ledger.get('batches',[]);covered={d for r in reports for d in r['requested_dois']}
    pending=sorted(set(dois)-covered);groups=[pending[i:i+100] for i in range(0,len(pending),100)]
    errors=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for start in range(0,len(groups),3):
            jobs=[pool.submit(batch,g) for g in groups[start:start+3]]
            for job in jobs:
                try:
                    found,report=job.result();rows.update(found);reports.append(report)
                except Exception as e:errors.append(str(e))
            if start%30==0 or errors or start+3>=len(groups):
                covered={d for r in reports for d in r['requested_dois']}
                ledger={'source':'OpenAlex predicted topics and keywords','corpus_dois':len(dois),'matched_dois':len(rows),
                        'complete':set(dois)<=covered and not errors,'batches':reports,'errors':errors,
                        'note':'Assignments are model predictions, not author-supplied keywords or expert-verified labels.'}
                save(DATA/'topic_metadata.json',rows);save(DATA/'coverage_topics.json',ledger)
                print(f'Topic metadata: {len(covered)}/{len(dois)} DOIs queried, {len(rows)} matched, errors={len(errors)}',flush=True)
            if errors:raise RuntimeError(errors)
    print('Topic collection complete.',flush=True)
if __name__=='__main__':main()
