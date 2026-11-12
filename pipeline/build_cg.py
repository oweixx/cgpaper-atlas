"""Offline build of the approved CG corpus, analytics, downloads and website."""
import argparse,csv,gzip,json,re
from collections import Counter
from datetime import datetime,timezone
from openpyxl import Workbook
from cg_config import ROOT,DATA,VENUES,YEAR
from network import save
from metadata import merge_records
from taxonomy import classify_with_evidence,TAXONOMY,TOPICS,SUBTOPICS,VERSION,UNCLASSIFIED
from taxonomy_v1 import classify as baseline_classify
from geography import build_geography

def load(name,default=None):
    path=DATA/(name+'.json')
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default

def exports(papers,summary):
    columns=['id','venue','venues','year','publication_year','venue_years','venue_evidence','source_years','title','authors','article_kind','topics','subtopics','classification_version','classification_basis','doi','url','pdf_url','abstract','citation_count','citation_source','citation_updated','sources']
    def values(p):
        result=[]
        for c in columns:
            value=p.get(c)
            if isinstance(value,dict):value=json.dumps(value,ensure_ascii=False)
            elif isinstance(value,list):value='; '.join(value)
            if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')):value="'"+value
            result.append(value)
        return result
    folder=ROOT/'downloads';folder.mkdir(exist_ok=True)
    with gzip.open(folder/'cgpaper_atlas.csv.gz','wt',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(columns);writer.writerows(values(p) for p in papers)
    with gzip.open(folder/'cgpaper_atlas.jsonl.gz','wt',encoding='utf-8') as f:
        for p in papers:f.write(json.dumps(p,ensure_ascii=False)+'\n')
    book=Workbook(write_only=True);sheet=book.create_sheet('summary')
    for row in [('Built at',summary['built_at']),('Unique papers',len(papers)),('Counting','Venue memberships overlap. Overall totals count each publication once.'),('Citations','OpenAlex global indexed citation count; not CG-only citations'),('Country','Work-time affiliation, not nationality')]:sheet.append(row)
    sheet.append(['Venue','Memberships','First year','Last year'])
    for v,m in summary['venues'].items():sheet.append([v,m['count'],m['min_year'],m['max_year']])
    for name,rows in [('papers',papers)]+[(v,[p for p in papers if v in p['venues']]) for v in VENUES]:
        sheet=book.create_sheet(name);sheet.append(columns)
        for p in rows:sheet.append(values(p))
    book.save(folder/'cgpaper_atlas.xlsx')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--draft',action='store_true');args=parser.parse_args()
    dblp=load('dblp',[]);crossref=load('crossref',[])
    ledger={'dblp':load('coverage_dblp',[]),'crossref':load('coverage_crossref',[]),'openalex':load('coverage_enrichment',{})}
    if not args.draft:
        assert len(ledger['dblp'])==8 and all(p['complete'] for p in ledger['dblp'])
        assert len(ledger['crossref'])==4 and all(p['complete'] for p in ledger['crossref'])
        assert ledger['openalex'].get('complete'), 'Finish OpenAlex collection before publishing'
    papers,excluded,identity,issues=merge_records(dblp,crossref)
    enrichment=load('enrichment',{})
    topic_metadata=load('topic_metadata',{})
    if not args.draft:assert load('coverage_topics',{}).get('complete'), 'Finish topic metadata collection before publishing'
    evidence_shards={c:{} for c in '0123456789abcdef'}
    old_topics={};classification_counts=Counter()
    for p in papers:
        e=next((enrichment[d] for d in [p['doi']]+p['doi_aliases'] if d in enrichment),None)
        if e:
            for key in ['openalex_id','citation_count','citation_source','citation_updated','pdf_url']:p[key]=e[key]
            if not p['abstract']:p['abstract']=e['abstract']
            p['sources']=sorted(set(p['sources']+['OpenAlex']))
        old_topics[p['id']]=baseline_classify(p['title'])[0]
        classification=classify_with_evidence(p['title'],p['abstract'],topic_metadata.get(p['doi']))
        p['topics'],p['subtopics']=classification.pop('topics'),classification.pop('subtopics')
        p['classification_version']=classification['version'];p['classification_basis']=classification['basis']
        classification_counts[classification['basis']]+=1
        evidence_shards[p['id'][0]][p['id']]=classification
    papers.sort(key=lambda p:(-p['year'],p['venue'],p['title'].lower()))
    assert len({p['id'] for p in papers})==len(papers)
    summary={'built_at':datetime.now(timezone.utc).isoformat(),'total':len(papers),'min_year':min(p['year'] for p in papers),
             'max_year':max(max(p['venue_years'].values()) for p in papers),'current_year':YEAR,
             'with_abstract':sum(bool(p['abstract']) for p in papers),'with_citations':sum(p['citation_count'] is not None for p in papers),
             'with_pdf':sum(bool(p['pdf_url']) for p in papers),'with_doi':sum(bool(p['doi']) for p in papers),
             'with_multiple_venues':sum(len(p['venues'])>1 for p in papers),
             'review_title_matches':sum(p['article_kind']=='Survey / review' for p in papers),
             'venues':{},'unique_years':dict(sorted(Counter(p['year'] for p in papers).items())),
             'topics':TOPICS+['Other / Unclassified'],'subtopics':SUBTOPICS+['Other / Unclassified'],'taxonomy':{k:list(v) for k,v in TAXONOMY.items()},
             'coverage_note':'Eight approved publication venues. Journal coverage includes all in-scope research articles, including special issues associated with other conferences. Those conferences are not collected independently. DBLP and four exact Crossref ISSN inventories are audited. Historical indexing gaps and current-year publication delays remain; no claim of complete worldwide CG coverage.',
             'citation_note':'OpenAlex global indexed citation counts, matched by exact DOI. These include citations from outside this CG collection. Not Google Scholar counts or CG-only citations. N/A means unavailable; zero means the source returned zero. Retrieval time is recorded per paper.',
             'topic_note':'10 CG research areas and 30 subtopics combine specific title evidence, context-aware abstract rules, and OpenAlex model-generated keywords mapped to CG subjects. Open Topic evidence on a paper to inspect the phrases, source and version. These are automatic labels, not official tracks or expert-verified decisions. Uncertain papers remain unclassified. Source metadata availability differs by venue and year. Topic shares overlap; survey/review categories still use title keywords.',
             'classification':{'version':VERSION,'basis_counts':dict(classification_counts),'unclassified':classification_counts['needs-review'],'baseline_unclassified':sum(ts==[UNCLASSIFIED] for ts in old_topics.values())},
             'counting_note':'A paper can belong to a conference and a journal. Venue counts overlap; total counts use unique publication identities. Conference filters use event years; journal filters use bibliographic publication years. Combined views prioritize conference editions and count each publication once.'}
    for v,m in VENUES.items():
        rows=[p for p in papers if v in p['venues']];years=Counter(p['venue_years'][v] for p in rows)
        summary['venues'][v]={**m,'count':len(rows),'min_year':min(years),'max_year':max(years),'years':dict(sorted(years.items())),
                              'with_abstract':sum(bool(p['abstract']) for p in rows),'with_citations':sum(p['citation_count'] is not None for p in rows),
                              'no_indexed_years':[y for y in range(m['since'],YEAR+1) if y not in years]}
    ledger['excluded_nonpapers']=len(excluded);ledger['counting_note']=summary['counting_note']
    save(DATA/'papers.json',papers);save(DATA/'summary.json',summary);save(DATA/'excluded.json',excluded)
    save(DATA/'coverage.json',ledger);save(DATA/'identity_audit.json',identity)
    save(DATA/'issue_mapping.json',[{'journal':k[0],'volume':k[1],'issue':k[2],'conference':v[0],'edition':v[1],'evidence':v[2],'dblp_records':v[3],'method':'official publication announcement' if v[3]==0 else 'unanimous DBLP issue membership'} for k,v in issues.items()])
    save(DATA/'year_audit.json',[{'id':p['id'],'title':p['title'],'year':p['year'],'publication_year':p['publication_year'],'venue_years':p['venue_years'],'source_years':p['source_years'],'evidence':p['venue_evidence']} for p in papers if p['year']!=p['publication_year'] or any(y!=p['publication_year'] for ys in p['source_years'].values() for y in ys)])
    geo=build_geography(papers);save(DATA/'geography.json',geo)
    for prefix,entries in evidence_shards.items():save(DATA/'topic_evidence'/f'{prefix}.json',entries)
    audit={'version':VERSION,'total':len(papers),'baseline_unclassified':sum(ts==[UNCLASSIFIED] for ts in old_topics.values()),
           'unclassified':classification_counts['needs-review'],'basis_counts':dict(classification_counts),
           'changed_area_sets':sum(set(p['topics'])!=set(old_topics[p['id']]) for p in papers),
           'baseline_area_counts':dict(Counter(t for ts in old_topics.values() for t in ts)),
           'area_counts':dict(Counter(t for p in papers for t in p['topics'])),
           'by_venue':{},'by_abstract':{},
           'metadata_dois':len(topic_metadata),'metadata_collection_complete':load('coverage_topics',{}).get('complete',False),
           'note':'Coverage is not accuracy. Reference evaluation is AI-reviewed and reported separately. Local mapping uses no venue/year/country priors or paper-specific overrides; OpenAlex keyword predictions can use the source venue as input.'}
    for v in VENUES:
        rows=[p for p in papers if v in p['venues']]
        audit['by_venue'][v]={'papers':len(rows),'with_abstract':sum(bool(p['abstract']) for p in rows),'baseline_unclassified':sum(old_topics[p['id']]==[UNCLASSIFIED] for p in rows),'unclassified':sum(p['topics']==[UNCLASSIFIED] for p in rows)}
    for present in [True,False]:
        rows=[p for p in papers if bool(p['abstract'])==present]
        audit['by_abstract'][str(present)]={'papers':len(rows),'baseline_unclassified':sum(old_topics[p['id']]==[UNCLASSIFIED] for p in rows),'unclassified':sum(p['topics']==[UNCLASSIFIED] for p in rows)}
    save(DATA/'topic_classification_audit.json',audit)
    if not args.draft:
        exports(papers,summary)
        template=(ROOT/'pipeline/site.html').read_text(encoding='utf-8').replace('<!-- ANALYTICS -->',(ROOT/'pipeline/analytics.html').read_text(encoding='utf-8'))
        for name in ['index.html','explorer.html','by_year.html','research_areas.html','global_research.html','dataset_preview.html']:
            (ROOT/name).write_text(template,encoding='utf-8',newline='\n')
        from write_docs import write_docs
        write_docs(summary,geo,ledger)
    print(json.dumps({'total':len(papers),'venues':{v:m['count'] for v,m in summary['venues'].items()},'overlapping':summary['with_multiple_venues'],'abstracts':summary['with_abstract'],'citations':summary['with_citations'],'geography':geo['coverage']},indent=2))
if __name__=='__main__':main()
