"""Identity, scope and edition rules for overlapping CG publication venues."""
import re,unicodedata,hashlib,json
from collections import defaultdict,Counter
from urllib.parse import unquote
from cg_config import VENUES,YEAR,DATA
CONFERENCES=[v for v,m in VENUES.items() if m['kind']=='conference']
EXCLUDED_TOC={
 'https://dblp.org/db/conf/siggraph/siggraph2003':'Sketches & Applications proceedings, not Technical Papers',
 'https://dblp.org/db/conf/siggrapha/siggrapha2019courses':'Courses proceedings, not Technical Papers',
}
NONPAPER=re.compile(r'^(?:editorial\b|guest editor|guest co.editor|from the editor|editor.in.chief|message from|preface\b|foreword\b|introduction to (?:the|this) (?:special|issue)|special issue (?:on|of)\b|table of contents|contents\b|author index|subject index|front (?:matter|cover)|back (?:matter|cover)|correction(?:s)?\b|corrigendum\b|errat(?:a|um)\b|retraction\b|reviewer (?:acknowledg|thanks)|acknowledg|call for papers|in memoriam|obituary|book review|calendar\b|news\b|conference (?:report|announcement))',re.I)
SURVEY=re.compile(r'\bsurvey\b|\breview of\b|\bsystematic review\b|\bscoping review\b|state.of.the.art|\ba review\b',re.I)
ADMIN=re.compile(r'^session details:|\beditor[’\x27]s note\b|\b(?:note|message) from (?:the )?(?:new )?editor|\bguest editors?\b|\beditorial(?: note)?(?:$| for|:)|^2019_editorial_v2$|^(?:welcome(?:\b|:)|farewell and new eic|state of the journal|ieee visualization and graphics technical committee)|^(?:ieee (?:vr|vis)|siggraph|eurographics|pacific graphics)\s*\d{4}$',re.I)

def normalize_doi(value):
    value=unquote(value or '').lower()
    return re.sub(r'\s+','',re.sub(r'^https?://(?:dx\.)?doi\.org/','',value))

def title_key(s):
    return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower())

def author_signature(names):
    return tuple(sorted(title_key(a) for a in names))

def edition(p,venue):
    stem={'SIGGRAPH':'siggraph','SIGGRAPH Asia':'siggrapha','Eurographics':'eg','Pacific Graphics':'pg'}[venue]
    stream=VENUES[venue]['stream']
    for toc in p.get('tocs',[]):
        m=re.fullmatch(r'https://dblp.org/db/'+stream+'/'+stem+r'((?:19|20)\d{2})',toc)
        if m:return int(m[1]),toc+'.html','conference proceedings edition'
    return p['publication_year'],p['source_url'],'DBLP conference-stream membership and publication year'

def merge_records(dblp,crossref):
    papers=[];by_doi={};by_title=defaultdict(list);excluded=[];identity=[]
    # Infer an issue's conference only when all DBLP entries in that issue agree.
    issues=defaultdict(list)
    for p in dblp:
        for v in p['venues']:
            if VENUES[v]['kind']=='journal' and p.get('volume') and p.get('issue'):
                issues[v,p['volume'],p['issue']].append(p)
    issue_map={}
    for key,rows in issues.items():
        memberships=[tuple((v,edition(p,v)[0]) for v in p['venues'] if v in CONFERENCES) for p in rows]
        if len(rows)>=5 and len(set(memberships))==1 and len(memberships[0])==1:
            url=rows[0]['tocs'][0]+'.html' if rows[0].get('tocs') else rows[0]['source_url']
            issue_map[key]=(*memberships[0][0],url,len(rows))
    overrides=DATA/'issue_overrides.json'
    if overrides.exists():
        for r in json.loads(overrides.read_text(encoding='utf-8')):
            issue_map[r['journal'],r['volume'],r['issue']]=(r['conference'],r['edition'],r['evidence'],0)
    for source,records in [('DBLP',dblp),('Crossref',crossref)]:
        for original in records:
            p=dict(original)
            excluded_toc=next((t for t in p.get('tocs',[]) if t in EXCLUDED_TOC),None)
            if excluded_toc:
                excluded.append({'source':source,'title':p['title'],'doi':p.get('doi'),'reason':EXCLUDED_TOC[excluded_toc],'evidence':excluded_toc+'.html'});continue
            p['doi']=normalize_doi(p.get('doi'))
            aliases=sorted({normalize_doi(d) for d in p.get('doi_aliases',[])+[p['doi']] if d})
            match=next((by_doi[d] for d in aliases if d in by_doi),None)
            if match is None and p.get('authors'):
                key=(title_key(p['title']),author_signature(p['authors']))
                candidates=[q for q in by_title[key] if (not aliases or not q['doi']) and set(p['venues'])&set(q['venues']) and abs(p['publication_year']-q['publication_year'])<=1]
                if len(candidates)==1:
                    match=candidates[0];identity.append({'title':p['title'],'doi':p['doi'],'reason':'Exact normalized title and full author list, shared venue and adjacent publication year; one record lacks DOI'})
            years={v:edition(p,v)[0] if v in CONFERENCES else p['publication_year'] for v in p['venues']}
            evidence={v:edition(p,v)[1] if v in CONFERENCES else p['source_url'] for v in p['venues']}
            if source=='Crossref':
                for v in list(p['venues']):
                    issue=issue_map.get((v,str(p.get('volume','')),str(p.get('issue',''))))
                    if issue:
                        event,y,url,n=issue
                        if event not in p['venues']:p['venues']=[*p['venues'],event]
                        years[event]=y;evidence[event]=url
            if match:
                for v in p['venues']:
                    if v not in match['venues']:match['venues'].append(v);match['venue_years'][v]=years[v];match['venue_evidence'][v]=evidence[v]
                match['sources']=sorted(set(match['sources']+[source]))
                match['source_years'].setdefault(source,[])
                match['source_years'][source]=sorted(set(match['source_years'][source]+[p['publication_year']]))
                if not match.get('abstract'):match['abstract']=p.get('abstract','')
                if not match.get('pages'):match['pages']=p.get('pages','')
                if not match['doi']:match['doi']=p['doi']
                match['doi_aliases']=sorted(set(match['doi_aliases']+aliases))
                for d in match['doi_aliases']:by_doi[d]=match
            else:
                p.update(doi_aliases=aliases,venue_years=years,venue_evidence=evidence,sources=[source],source_years={source:[p['publication_year']]})
                p.setdefault('abstract','');papers.append(p)
                by_title[title_key(p['title']),author_signature(p['authors'])].append(p)
                for d in aliases:by_doi[d]=p
    retained=[]
    for p in papers:
        reason=''
        if not p['title'] or not any(p['authors']):reason='Missing title or author list'
        elif not 1900<=p['publication_year']<=YEAR:reason='Undated or future-year publication'
        elif NONPAPER.search(p['title']) or ADMIN.search(p['title']):reason='Editorial, session listing, correction, front matter or other non-research item'
        elif 'TOG' in p['venues'] and p.get('volume')=='36' and p.get('issue')=='4' and p['doi'].startswith('10.1145/3072959.') and p.get('pages')=='1':reason='TOG 36(4) one-page presentation record; original full research article remains separate'
        if reason:
            excluded.append({'title':p['title'],'doi':p['doi'],'reason':reason,'evidence':p['source_url']});continue
        p['venues']=sorted(set(p['venues']),key=list(VENUES).index)
        p['venue']=p['venues'][0]
        p['year']=p['venue_years'][p['venue']]
        p['year_basis']='Conference edition where known; otherwise bibliographic publication year'
        p['article_kind']='Survey / review' if SURVEY.search(p['title']) else 'Research / other'
        p['id']=hashlib.sha256((p['doi'] or p['source_url']).encode()).hexdigest()[:20]
        p['url']='https://doi.org/'+p['doi'] if p['doi'] else p['source_url']
        p['pdf_url']='';p['citation_count']=None;p['citation_source']=None;p['citation_updated']=None
        retained.append(p)
    return retained,excluded,identity,issue_map
