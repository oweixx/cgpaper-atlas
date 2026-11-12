"""Semantic keyword mapping with an evidence-based local fallback."""
import re
from taxonomy_rules import TOPICS,SUBTOPICS,TAXONOMY,UNCLASSIFIED,normalize,RULES
from taxonomy_rules import classify_with_evidence as rule_classify
from topic_keyword_map import ALIASES

VERSION='cg-topics-v3.0'
MIN_KEYWORD_SCORE=0.65
KEYWORD_LIMIT=5
CODE_INFO={code:(area,name) for code,area,name,_ in RULES}
KEYWORD_MAP={}
for code,names in ALIASES.items():
    for name in names:KEYWORD_MAP.setdefault(normalize(name),set()).add(code)

# Render techniques contribute both a task area and a method/application area.
for word in ['real time rendering','interactive rendering','volume rendering','direct volume rendering','neural rendering','gaussian splatting','3d gaussian splatting','2d gaussian splatting','gaussian avatars','3d gaussian avatars','neural avatars','radiance fields','neural radiance fields']:
    KEYWORD_MAP.setdefault(word,set()).add('R1')

def keyword_codes(name,all_keywords):
    normalized=normalize(name)
    codes=set(KEYWORD_MAP.get(normalized,[]))
    if not codes:
        codes={code for code,_,_,pattern in RULES if pattern.search(normalized)}
    if normalized=='material design':
        structural=any(re.search(r'mechanic|metamaterial|structur|topology|microstruct',normalize(k['display_name'])) for k in all_keywords)
        codes.discard('R2' if structural else 'F2')
    if normalized=='radiance fields' and not any(re.search(r'neural|gaussian|nerf|deep learn|machine learn',normalize(k['display_name'])) for k in all_keywords):
        codes.discard('N1')
    if normalized=='light fields':
        subjects=' '.join(normalize(k['display_name']) for k in all_keywords)
        if re.search(r'light transport|light scattering|photon|global illumination',subjects) and not re.search(r'camera|imaging|photograph|display',subjects):codes.discard('I2')
    return codes

def classify_with_evidence(title,abstract='',aboutness=None,min_score=MIN_KEYWORD_SCORE,limit=KEYWORD_LIMIT):
    keywords=(aboutness or {}).get('keywords',[])
    usable=[(i,k) for i,k in enumerate(keywords) if isinstance(k.get('score'),(int,float)) and k['score']>=min_score and i<limit]
    if not usable:
        result=rule_classify(title,abstract)
        result['version']=VERSION
        result['metadata_available']=bool(aboutness)
        result['fallback_reason']='No qualifying OpenAlex keyword evidence'
        return result
    evidence=[]
    for rank,keyword in usable:
        for code in sorted(keyword_codes(keyword['display_name'],keywords)):
            if code in {'P2','P3'} and rank>=2:
                # Routine study/evaluation keywords are often ancillary.
                continue
            if code=='A1' and normalize(keyword['display_name']).startswith('locomotion') and re.search(r'virtual environment|virtual reality|immersive|\bvr\b',normalize(title)) and not re.search(r'avatar|character|animation',normalize(title)):
                continue
            area,name=CODE_INFO[code]
            evidence.append({'area':area,'subtopic':name,'basis':'openalex_keyword',
                             'terms':[keyword['display_name']],'snippet':keyword['display_name'],
                             'source_url':keyword['id'],'source_score':keyword['score'],'source_rank':rank+1})
    base=rule_classify(title,abstract)
    supported={e['area'] for e in evidence}
    for e in base['evidence']:
        if e['basis']=='title':
            # Weak object/device words can name an input rather than the target.
            if e['area'] not in supported and evidence and all(re.fullmatch(r'polygon\w*|lidar',t) for t in e['terms']):continue
            evidence.append(e)
        elif e['area'] in supported or not supported:
            evidence.append(e)
    areas=[a for a in TOPICS if any(e['area']==a for e in evidence)]
    details=[t for t in SUBTOPICS if any(e['subtopic']==t for e in evidence)]
    return {'topics':areas or [UNCLASSIFIED],'subtopics':details or [UNCLASSIFIED],
            'version':VERSION,'basis':('metadata-supported' if supported else base['basis']) if evidence else 'needs-review',
            'evidence':evidence,'review_candidates':[], 'abstract_available':bool(abstract),
            'metadata_available':True,'openalex_id':aboutness['openalex_id'],
            'retrieved_at':aboutness['retrieved_at'],'primary_topic':aboutness.get('primary_topic',{}),
            'source_keywords':[k for _,k in usable]}

def classify(title,abstract='',aboutness=None):
    result=classify_with_evidence(title,abstract,aboutness)
    return result['topics'],result['subtopics']
