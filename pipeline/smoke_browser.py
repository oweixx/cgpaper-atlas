"""Functional and visual checks against local or deployed CG Paper Atlas."""
import argparse,csv,json
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
from playwright.sync_api import sync_playwright,expect
from cg_config import DATA,VENUES,ROOT

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base-url',default='http://127.0.0.1:8767/');parser.add_argument('--output-dir',type=Path,default=ROOT/'docs');args=parser.parse_args()
    out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    papers=json.loads((DATA/'papers.json').read_text(encoding='utf-8'));s=json.loads((DATA/'summary.json').read_text(encoding='utf-8'));g=json.loads((DATA/'geography.json').read_text(encoding='utf-8'))
    checks=[];errors=[];requests=[]
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:requests.append(r.url))
        page.goto(args.base_url,wait_until='domcontentloaded')
        expect(page.locator('#result-status')).to_have_text(f"{s['total']:,} papers in this view",timeout=180000)
        expect(page.locator('#paper-body tr')).to_have_count(25)
        expect(page.locator('#venue-filters input')).to_have_count(8)
        expect(page.locator('#country')).to_be_enabled(timeout=60000)
        checks.append('Eight approved venues and the full deduplicated corpus load')
        page.screenshot(path=str(out/'preview-desktop.png'))
        country_papers=[p for p in papers if 'KR' in g['papers'].get(p['id'],{}).get('countries',{})]
        page.locator('#country').select_option('KR')
        expect(page.locator('#result-status')).to_have_text(f'{len(country_papers):,} papers in this view')
        assert any(len(g['papers'][p['id']]['countries'])>1 and len(p['venues'])>1 for p in country_papers)
        checks.append('Country filter includes international collaborations and deduplicates overlapping venues')
        for v in VENUES:
            if v!='SIGGRAPH':page.locator(f'#venue-filters input[value="{v}"]').uncheck()
        page.locator('#year-from').fill('2023');page.locator('#year-to').fill('2023');page.locator('#year-to').press('Tab')
        page.locator('#topic').select_option('Rendering')
        page.locator('#min-citations').fill('5');page.locator('#sort').select_option('citations')
        country_selection=[p for p in country_papers if 'SIGGRAPH' in p['venues'] and p['venue_years']['SIGGRAPH']==2023 and 'Rendering' in p['topics'] and p['citation_count'] is not None and p['citation_count']>=5]
        assert country_selection
        expect(page.locator('#result-status')).to_have_text(f'{len(country_selection):,} papers in this view')
        page.evaluate('window.scrollTo(0, 0)');page.screenshot(path=str(out/'preview-country.png'),full_page=True)
        with page.expect_download() as event:page.locator('#export-filtered').click()
        event.value.save_as(str(out/'country-papers.csv'))
        with (out/'country-papers.csv').open(encoding='utf-8-sig',newline='') as f:
            rows=list(csv.DictReader(f))
            assert {r['doi'] for r in rows}=={p['doi'] for p in country_selection}
            assert all('KR' in r['affiliation_country_codes'].split('; ') and r['year']=='2023' for r in rows)
            assert all('South Korea' in r['affiliation_countries'] for r in rows)
        state=parse_qs(urlsplit(page.url).query)
        assert state['country']==['KR'] and state['min-citations']==['5'] and state['sort']==['citations']
        page.reload(wait_until='domcontentloaded')
        expect(page.locator('#result-status')).to_have_text(f'{len(country_selection):,} papers in this view',timeout=180000)
        expect(page.locator('#country')).to_have_value('KR');expect(page.locator('#min-citations')).to_have_value('5');expect(page.locator('#sort')).to_have_value('citations')
        sample_country=country_selection[0]
        page.locator('#subtopic').select_option(sample_country['subtopics'][0]);page.locator('#article-kind').select_option(sample_country['article_kind'])
        page.locator('#query').fill(sample_country['doi']);expect(page.locator('#result-status')).to_have_text('1 papers in this view')
        assert page.locator('#mini-chart text[text-anchor="end"]').all_text_contents()==['1','0']
        checks.append('Country combines with venue, year, topic, subtopic, category, query and citations; CSV and shared URL agree')
        page.locator('#reset').click();page.locator('#country').select_option('unknown')
        unknown=sum(not g['papers'].get(p['id'],{}).get('countries') for p in papers)
        expect(page.locator('#result-status')).to_have_text(f'{unknown:,} papers in this view')
        page.locator('#reset').click()
        expect(page.locator('#country')).to_have_value('');expect(page.locator('#sort')).to_have_value('newest')
        expect(page.locator('#result-status')).to_have_text(f"{s['total']:,} papers in this view")
        assert 'country' not in parse_qs(urlsplit(page.url).query)
        checks.append('Unknown affiliations include unmatched papers; reset clears country and shared URL state')
        for v in VENUES:
            if v not in ['SIGGRAPH','TOG']:page.locator(f'#venue-filters input[value="{v}"]').uncheck()
        expected=sum(bool({'SIGGRAPH','TOG'}&set(p['venues'])) for p in papers)
        expect(page.locator('#result-status')).to_have_text(f'{expected:,} papers in this view')
        assert expected<s['venues']['SIGGRAPH']['count']+s['venues']['TOG']['count']
        checks.append('SIGGRAPH and TOG union counts shared papers once')
        sample=next(p for p in papers if p['title'].lower().startswith('3d gaussian splatting for real-time'))
        page.locator('#query').fill(sample['doi']);expect(page.locator('#result-status')).to_have_text('1 papers in this view')
        expect(page.locator('#paper-body')).to_contain_text(sample['title'])
        if sample['abstract']:
            page.locator('#paper-body .abstract summary').click();expect(page.locator('#paper-body .abstract[open] p')).not_to_be_empty()
        checks.append('Known Gaussian Splatting paper resolves once across conference and journal')
        assert not any('/data/topic_evidence/' in url for url in requests), 'Evidence should not load until requested'
        evidence=page.locator('#paper-body .topic-evidence')
        evidence.locator('summary').click()
        expect(evidence).to_contain_text(s['classification']['version'])
        expect(evidence).to_contain_text('OpenAlex keyword')
        expect(evidence).to_contain_text('Neural rendering & radiance fields')
        expect(evidence).to_contain_text('not the accuracy')
        count=sum('/data/topic_evidence/' in url for url in requests)
        assert count==1
        evidence.locator('summary').click();evidence.locator('summary').click()
        assert sum('/data/topic_evidence/' in url for url in requests)==count
        evidence.screenshot(path=str(out/'preview-topic-evidence.png'))
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        assert evidence.bounding_box()['width']>=300, 'Mobile evidence should use the full paper width'
        evidence.screenshot(path=str(out/'preview-topic-evidence-mobile.png'))
        page.set_viewport_size({'width':1440,'height':1000})
        checks.append('Topic evidence loads on demand once, shows source and version, and fits mobile')
        page.locator('#query').fill('no-such-paper-abc-987654321');expect(page.locator('#result-status')).to_have_text('0 papers in this view')
        page.locator('#reset').click();expect(page.locator('#result-status')).to_have_text(f"{s['total']:,} papers in this view")
        checks.append('Empty results and reset work')
        for v in VENUES:
            if v!='CGF':page.locator(f'#venue-filters input[value="{v}"]').uncheck()
        page.locator('#year-from').fill('2025');page.locator('#year-to').fill('2025');page.locator('#year-to').press('Tab')
        expected=s['venues']['CGF']['years']['2025'];expect(page.locator('#result-status')).to_have_text(f'{expected:,} papers in this view')
        page.locator('#article-kind').select_option('Survey / review')
        expected=sum('CGF' in p['venues'] and p['venue_years']['CGF']==2025 and p['article_kind']=='Survey / review' for p in papers)
        expect(page.locator('#result-status')).to_have_text(f'{expected:,} papers in this view')
        with page.expect_download() as event:page.locator('#export-filtered').click()
        event.value.save_as(str(out/'filtered.csv'))
        with (out/'filtered.csv').open(encoding='utf-8-sig',newline='') as f:
            rows=list(csv.DictReader(f));assert len(rows)==expected and all(r['year']=='2025' for r in rows)
            assert all(r['topics'] and r['subtopics'] and r['classification_version']==s['classification']['version'] for r in rows)
        checks.append('Journal year, review category and exported paper rows agree')
        page.locator('#reset').click();page.locator('#next').click();expect(page.locator('#page-info')).to_contain_text('Page 2 ')
        page.locator('#page-size').select_option('100');expect(page.locator('#paper-body tr')).to_have_count(100)
        checks.append('Pagination and page size work')
        page.get_by_role('link',name='Research trends',exact=True).click()
        expect(page.locator('#trend-chart svg')).to_be_visible()
        expect(page.locator('#trends-body tr')).to_have_count(s['max_year']-s['min_year']+1)
        row=page.locator('#trends-body tr').filter(has=page.get_by_text('2025',exact=True))
        expect(row.locator('td').last).to_have_text(f"{s['unique_years']['2025']:,}")
        checks.append('Annual venue memberships and unique annual totals remain separate')
        page.get_by_role('link',name='Research areas',exact=True).click()
        page.locator('#research-venue').select_option('SIGGRAPH');page.locator('#research-from').fill('2023');page.locator('#research-to').fill('2023');page.locator('#research-to').press('Tab')
        page.locator('#research-level').select_option('subtopics');page.locator('#research-focus').select_option('Neural rendering & radiance fields')
        selected=[p for p in papers if 'SIGGRAPH' in p['venues'] and p['venue_years']['SIGGRAPH']==2023]
        expected=sum('Neural rendering & radiance fields' in p['subtopics'] for p in selected)
        expect(page.locator('#research-kpis .stat-value').nth(1)).to_have_text(f'{expected:,}')
        page.screenshot(path=str(out/'preview-research.png'))
        with page.expect_download() as event:page.locator('#research-export').click()
        event.value.save_as(str(out/'research.csv'))
        with (out/'research.csv').open(encoding='utf-8-sig',newline='') as f:
            r=next(r for r in csv.DictReader(f) if r['topic']=='Neural rendering & radiance fields')
            assert abs(float(r['share_percent'])-100*expected/len(selected))<1e-9
        page.locator('#research-papers').click();expect(page.locator('#result-status')).to_have_text(f'{expected:,} papers in this view')
        checks.append('Detailed CG topic counts, percentage export and paper drilldown agree')
        assert not any(url.endswith('/data/world.json') for url in requests)
        page.get_by_role('link',name='Global research',exact=True).click();expect(page.locator('#world-map svg')).to_be_visible(timeout=60000)
        assert sum(url.endswith('/data/geography.json') for url in requests)==2, 'Each of the two page loads should fetch affiliations once, shared by explorer and map'
        page.locator('#world-venue').select_option('SIGGRAPH');page.locator('#world-from').fill('2023');page.locator('#world-to').fill('2023');page.locator('#world-to').press('Tab')
        page.locator('#world-topic').select_option('Rendering')
        country=[p for p in selected if 'KR' in g['papers'].get(p['id'],{}).get('countries',{})]
        focused=[p for p in country if 'Rendering' in p['topics']]
        ids={a for p in focused for a in g['papers'][p['id']]['countries']['KR']}
        row=page.locator('#world-table tr').filter(has=page.locator('[data-country="KR"]'))
        expect(row.locator('td').nth(1)).to_have_text(f'{len(ids):,}');expect(row.locator('td').nth(2)).to_have_text(f'{len(focused):,}')
        expect(row.locator('td').nth(4)).to_have_text(f'{100*len(focused)/len(country):.1f}%')
        page.locator('#world-map [data-country="KR"]').click();expect(page.locator('#world-country')).to_have_value('KR')
        page.screenshot(path=str(out/'preview-world.png'))
        with page.expect_download() as event:page.locator('#world-export').click()
        event.value.save_as(str(out/'countries.csv'))
        with (out/'countries.csv').open(encoding='utf-8-sig',newline='') as f:
            kr=next(r for r in csv.DictReader(f) if r['country_code']=='KR');assert int(kr['unique_authors'])==len(ids)
        checks.append('Country map, deduplicated author IDs, topic share and CSV agree with the affiliation snapshot')
        page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        page.screenshot(path=str(out/'preview-world-mobile.png'))
        page.locator('#world-from').fill('1974');page.locator('#world-to').fill('1974');page.locator('#world-to').press('Tab')
        # Test an empty, pre-series range without treating unknown countries as zero.
        page.locator('#world-venue').select_option('SIGGRAPH Asia');expect(page.locator('#world-table')).to_contain_text('No affiliation data')
        checks.append('Empty geographic selections are handled explicitly')
        for view in ['Research trends','Research areas','About the data','Paper explorer']:
            page.get_by_role('link',name=view,exact=True).click();assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'),view
        page.locator('#reset').click();page.locator('#page-size').select_option('25');page.screenshot(path=str(out/'preview-mobile.png'))
        page.locator('#country').select_option('KR');expect(page.locator('#result-status')).to_have_text(f'{len(country_papers):,} papers in this view')
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        page.locator('aside.filters').screenshot(path=str(out/'preview-country-mobile.png'))
        checks.append('All views fit the mobile viewport')
        page.get_by_role('link',name='About the data',exact=True).click();expect(page.locator('#coverage-body tr')).to_have_count(8)
        checks.append('Eight-venue provenance and coverage are visible')
        failed=browser.new_page();failed.on('pageerror',lambda e:errors.append(str(e)))
        failed.route('**/data/topic_evidence/*.json',lambda route:route.abort())
        failed.goto(args.base_url+'?q='+sample['doi'],wait_until='domcontentloaded')
        expect(failed.locator('#result-status')).to_have_text('1 papers in this view',timeout=180000)
        failed.locator('.topic-evidence summary').click()
        expect(failed.locator('[data-retry-evidence]')).to_be_visible()
        failed.unroute('**/data/topic_evidence/*.json');failed.locator('[data-retry-evidence]').click()
        expect(failed.locator('.topic-evidence')).to_contain_text('OpenAlex keyword')
        checks.append('Failed evidence requests can be retried without affecting paper results')
        failed.route('**/data/geography.json',lambda route:route.abort())
        failed.goto(args.base_url+'?country=KR',wait_until='domcontentloaded')
        expect(failed.locator('#result-status')).to_contain_text('Country data unavailable',timeout=180000)
        expect(failed.locator('#export-filtered')).to_be_disabled();expect(failed.locator('#country-retry')).to_be_visible()
        assert parse_qs(urlsplit(failed.url).query)['country']==['KR']
        failed.unroute('**/data/geography.json');failed.locator('#country-retry').click()
        expect(failed.locator('#result-status')).to_have_text(f'{len(country_papers):,} papers in this view',timeout=60000)
        expect(failed.locator('#country')).to_have_value('KR');expect(failed.locator('#export-filtered')).to_be_enabled()
        checks.append('Affiliation failure preserves the requested country, blocks misleading exports and supports retry')
        failed.goto(args.base_url+'?country=ZZ',wait_until='domcontentloaded')
        expect(failed.locator('#result-status')).to_have_text('0 papers in this view',timeout=180000)
        expect(failed.locator('#country')).to_have_value('ZZ')
        assert parse_qs(urlsplit(failed.url).query)['country']==['ZZ']
        checks.append('Unindexed country URLs show no matches instead of silently broadening to all countries')
        failed.close()
        browser.close()
    assert not errors,errors
    report={'base_url':args.base_url,'papers':len(papers),'passed':checks,'browser_errors':errors}
    (out/'browser-qa.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
