"""Compare area labels to openly attributed AI-reviewed reference sets."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from cg_config import DATA, ROOT
from taxonomy import classify, TOPICS, VERSION, UNCLASSIFIED
from taxonomy_v1 import classify as baseline
from taxonomy_rules import classify as rules_classify

def metrics(pairs):
    tp = fp = fn = exact = 0
    for gold, predicted in pairs:
        tp += len(gold & predicted); fp += len(predicted - gold); fn += len(gold - predicted)
        exact += gold == predicted
    return {'papers':len(pairs),'true_positive':tp,'false_positive':fp,'false_negative':fn,
            'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,
            'micro_f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
            'exact_match':exact/len(pairs) if pairs else None}

def evaluate(papers, reference):
    lookup={p['id']:p for p in papers}; results={}
    metadata=json.loads((DATA/'topic_metadata.json').read_text(encoding='utf-8')) if (DATA/'topic_metadata.json').exists() else {}
    for name, classifier in [('v1_title',lambda p:baseline(p['title'])[0]),
                             ('rules_title_abstract',lambda p:rules_classify(p['title'],p['abstract'])[0]),
                             ('v3_hybrid',lambda p:classify(p['title'],p['abstract'],metadata.get(p['doi']))[0])]:
        rows=[]
        for r in reference['records']:
            p=lookup[r['id']]
            assert hashlib.sha256((p['title']+'\n'+p['abstract']).encode()).hexdigest()==r['text_sha256'],r['id']
            prediction=[t for t in classifier(p) if t!=UNCLASSIFIED]
            rows.append({'id':p['id'],'title':p['title'],'venue':p['venue'],'year':p['year'],
                         'abstract_available':bool(p['abstract']),'reference':r['topics'],'predicted':prediction})
        pairs=lambda subset:[(set(r['reference']),set(r['predicted'])) for r in subset]
        results[name]={'overall':metrics(pairs(rows)),
            'by_area':{t:metrics([(a&{t},b&{t}) for a,b in pairs(rows)]) for t in TOPICS},
            'by_venue':{v:metrics(pairs([r for r in rows if r['venue']==v])) for v in sorted({r['venue'] for r in rows})},
            'by_abstract':{str(b):metrics(pairs([r for r in rows if r['abstract_available']==b])) for b in [True,False]},
            'by_era':{era:metrics(pairs([r for r in rows if (r['year']>=2015)==recent])) for era,recent in [('before_2015',False),('2015_onward',True)]},
            'disagreements':[r for r in rows if set(r['reference'])!=set(r['predicted'])]}
    return {'classifier_version':VERSION,
            'classifier_sha256':{name:hashlib.sha256((ROOT/'pipeline'/name).read_bytes()).hexdigest() for name in ['taxonomy.py','taxonomy_rules.py','topic_keyword_map.py']},
            'metadata_sha256':hashlib.sha256((DATA/'topic_metadata.json').read_bytes()).hexdigest(),
            'reference_role':reference['role'],'annotator':reference['annotator'],
            'sampling':reference['sampling'],'limitation':'AI-reviewed reference labels, not independent expert ground truth; this small stratified sample is not a population accuracy estimate. Area-level metrics do not validate every subtopic.',
            'models':results}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--reference',default='topic_reference_dev.json');parser.add_argument('--output',type=Path,default=ROOT/'.cache/topic-evaluation-dev.json');args=parser.parse_args()
    papers=json.loads((DATA/'papers.json').read_text(encoding='utf-8'))
    reference=json.loads((DATA/args.reference).read_text(encoding='utf-8'))
    report=evaluate(papers,reference)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')
    print(json.dumps({k:v['overall'] for k,v in report['models'].items()},indent=2))
    for r in report['models']['v3_hybrid']['disagreements']:
        print(json.dumps({'title':r['title'],'extra':sorted(set(r['predicted'])-set(r['reference'])),'missing':sorted(set(r['reference'])-set(r['predicted']))},ensure_ascii=True))
if __name__=='__main__':main()
