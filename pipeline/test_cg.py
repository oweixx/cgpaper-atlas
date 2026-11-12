import unittest
from metadata import merge_records,normalize_doi
from taxonomy import classify,classify_with_evidence,VERSION
from geography import build_geography
from collect_openalex import normalize_authorships

def record(doi='10.123/a',title='Real-time rendering',venues=None,year=2020,**extra):
    return {'doi':doi,'title':title,'venues':venues or ['TOG'],'publication_year':year,'authors':['Ada Lovelace','Alan Turing'],'source_url':'https://dblp.org/rec/example','tocs':[],'volume':'','issue':'',**extra}

class CGTests(unittest.TestCase):
    def test_conference_journal_identity(self):
        p=record(venues=['SIGGRAPH','TOG'])
        rows,*_=merge_records([p],[record()])
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['venues'],['SIGGRAPH','TOG'])
    def test_edition_differs_from_publication(self):
        p=record(venues=['Eurographics','CGF'],year=1982,tocs=['https://dblp.org/db/conf/eurographics/eg1981'])
        r=merge_records([p],[])[0][0]
        self.assertEqual(r['year'],1981);self.assertEqual(r['venue_years']['CGF'],1982)
    def test_sketches_excluded(self):
        p=record(venues=['SIGGRAPH'],year=2003,tocs=['https://dblp.org/db/conf/siggraph/siggraph2003'])
        rows,excluded,*_=merge_records([p],[])
        self.assertFalse(rows);self.assertIn('Sketches',excluded[0]['reason'])
    def test_courses_excluded(self):
        p=record(venues=['SIGGRAPH Asia'],year=2019,tocs=['https://dblp.org/db/conf/siggrapha/siggrapha2019courses'])
        self.assertFalse(merge_records([p],[])[0])
    def test_pg_external_journal_in_scope(self):
        p=record(venues=['Pacific Graphics'],year=2005,container='Vis. Comput.')
        self.assertEqual(merge_records([p],[])[0][0]['venues'],['Pacific Graphics'])
    def test_distinct_dois_stay_distinct(self):
        self.assertEqual(len(merge_records([record('10.123/a')],[record('10.123/b')])[0]),2)
    def test_doiless_exact_identity(self):
        rows=merge_records([record('')],[record()])[0]
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['doi'],'10.123/a')
    def test_different_authors_not_merged(self):
        self.assertEqual(len(merge_records([record('',authors=['Someone Else'])],[record()])[0]),2)
    def test_issue_mapping_requires_unanimity(self):
        ps=[record(f'10.123/{i}',venues=['SIGGRAPH','TOG'],volume='39',issue='4') for i in range(5)]
        new=record('10.123/new',volume='39',issue='4')
        out=merge_records(ps,[new])[0]
        self.assertIn('SIGGRAPH',next(p for p in out if p['doi']==new['doi'])['venues'])
        ps.append(record('10.123/regular',volume='39',issue='4'))
        out=merge_records(ps,[new])[0]
        self.assertNotIn('SIGGRAPH',next(p for p in out if p['doi']==new['doi'])['venues'])
    def test_nonpapers_and_reviews(self):
        rows,excluded,*_=merge_records([record(title='Editorial'),record('10.123/r',title='A Survey of Neural Rendering')],[])
        self.assertEqual(len(excluded),1);self.assertEqual(rows[0]['article_kind'],'Survey / review')
    def test_doi_normalization(self):
        self.assertEqual(normalize_doi('https://doi.org/10.123/ A%20B'),'10.123/ab')
    def test_cg_topics_multilabel(self):
        areas,details=classify('3D Gaussian Splatting for Real-Time Radiance Field Rendering')
        self.assertIn('Rendering',areas);self.assertIn('Neural rendering & radiance fields',details)
        self.assertEqual(classify('An unfamiliar title')[0],['Other / Unclassified'])
    def test_roman_pagination_is_not_a_nonpaper_classifier(self):
        p=record(title='Learning to Stabilize Faces',venues=['CGF'],pages='i-iii')
        self.assertEqual(len(merge_records([p],[])[0]),1)
    def test_session_lists_and_one_page_presentation_records(self):
        ps=[record(title='Session details: Rendering'),record('10.1145/3072959.3126814',title='BundleFusion',volume='36',issue='4',pages='1')]
        self.assertFalse(merge_records(ps,[])[0])
    def test_authorship_dedup_and_missing(self):
        a=normalize_authorships({'authorships':[{'author':{'id':'https://openalex.org/A1'},'countries':['US']},{'author':{'id':'https://openalex.org/A1'},'institutions':[{'country_code':'KR'}]},{'author':{'id':'https://openalex.org/A2'},'countries':[]}]})
        self.assertEqual(a,[{'id':'A1','countries':['KR','US']},{'id':'A2','countries':[]}])
        g=build_geography([{'id':'p','doi':'10.1/a'},{'id':'q','doi':'10.1/b'}],source={'10.1/a':{'authors':a},'10.1/b':{'authors':a}},ledger={'complete':True})
        self.assertEqual(g['coverage']['unique_author_ids_with_country'],1)
        self.assertEqual(g['coverage']['authorships_with_country'],2)
class TopicTests(unittest.TestCase):
    def metadata(self,*keywords):
        return {'openalex_id':'https://openalex.org/W1','retrieved_at':'2026-11-13',
                'keywords':[{'id':f'https://openalex.org/keywords/{i}',
                             'display_name':name,'score':score} for i,(name,score) in enumerate(keywords)]}
    def test_motion_retargeting_is_not_image_retargeting(self):
        areas,_=classify('Motion retargeting for character animation')
        self.assertIn('Animation & Simulation',areas)
        self.assertNotIn('Images & Computational Photography',areas)
    def test_geometric_diffusion_is_not_a_generative_model(self):
        areas,_=classify('Anisotropic diffusion on triangle meshes')
        self.assertIn('Geometry & Modeling',areas)
        self.assertNotIn('Neural & Generative Graphics',areas)
    def test_neural_network_is_not_network_visualization(self):
        areas,_=classify('Neural networks for character animation')
        self.assertNotIn('Visualization & Visual Analytics',areas)
    def test_background_comparison_is_not_a_contribution(self):
        areas,_=classify('A new construction','Previous approaches used neural rendering. We propose mesh parameterization.')
        self.assertIn('Geometry & Modeling',areas)
        self.assertNotIn('Neural & Generative Graphics',areas)
    def test_missing_evidence_abstains(self):
        r=classify_with_evidence('A new approach')
        self.assertEqual(r['topics'],['Other / Unclassified'])
        self.assertEqual(r['basis'],'needs-review');self.assertFalse(r['evidence'])
    def test_haptic_rendering_is_not_light_transport(self):
        areas,_=classify('A new approach','',self.metadata(('Haptic rendering',.9)))
        self.assertIn('XR & Interaction',areas);self.assertNotIn('Rendering',areas)
    def test_external_evidence_retains_provenance(self):
        r=classify_with_evidence('A new approach','',self.metadata(('Gaussian splatting',.9)))
        self.assertIn('Neural & Generative Graphics',r['topics']);self.assertIn('Rendering',r['topics'])
        self.assertEqual(r['version'],VERSION)
        for e in r['evidence']:
            self.assertEqual(e['source_url'],'https://openalex.org/keywords/0')
            self.assertEqual(e['source_score'],.9);self.assertEqual(e['source_rank'],1)
    def test_low_score_cannot_create_external_label(self):
        low=classify('A new approach','',self.metadata(('Gaussian splatting',.64)))
        high=classify('A new approach','',self.metadata(('Gaussian splatting',.65)))
        self.assertEqual(low[0],['Other / Unclassified']);self.assertIn('Rendering',high[0])
    def test_keyword_order_is_not_replaced_by_score_sorting(self):
        r=classify('A new approach','',self.metadata(*([('Unmapped subject',.7)]*5+[('Gaussian splatting',1.0)])))
        self.assertEqual(r[0],['Other / Unclassified'])
    def test_unmapped_metadata_preserves_local_evidence(self):
        r=classify_with_evidence('Mesh parameterization','',self.metadata(('Unmapped subject',.9)))
        self.assertIn('Geometry & Modeling',r['topics'])
        self.assertTrue(any(e['basis']=='title' for e in r['evidence']))

if __name__=='__main__':unittest.main()
