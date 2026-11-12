"""Functional and visual checks against local or deployed CG Paper Atlas."""
import argparse,csv,json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from cg_config import DATA,VENUES,ROOT

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base-url',default='http://127.0.0.1:8767/');parser.add_argument('--output-dir',type=Path,default=ROOT/'docs');args=parser.parse_args()
    out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    papers=json.loads((DATA/'papers.json').read_text(encoding='utf-8'));s=json.loads((DATA/'summary.json').read_text(encoding='utf-8'));g=json.loads((DATA/'geography.json').read_text(encoding='utf-8'))
    checks=[];errors=[]
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(args.base_url,wait_until='domcontentloaded')
        expect(page.locator('#result-status')).to_have_text(f"{s['total']:,} papers in this view",timeout=180000)
        expect(page.locator('#paper-body tr')).to_have_count(25)
        expect(page.locator('#venue-filters input')).to_have_count(8)
        checks.append('Eight approved venues and the full deduplicated corpus load')
        page.screenshot(path=str(out/'preview-desktop.png'))
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
            page.locator('#paper-body summary').click();expect(page.locator('#paper-body details[open] p')).not_to_be_empty()
        checks.append('Known Gaussian Splatting paper resolves once across conference and journal')
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
        page.get_by_role('link',name='Global research',exact=True).click();expect(page.locator('#world-map svg')).to_be_visible(timeout=60000)
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
        checks.append('All views fit the mobile viewport')
        page.get_by_role('link',name='About the data',exact=True).click();expect(page.locator('#coverage-body tr')).to_have_count(8)
        checks.append('Eight-venue provenance and coverage are visible')
        browser.close()
    assert not errors,errors
    report={'base_url':args.base_url,'papers':len(papers),'passed':checks,'browser_errors':errors}
    (out/'browser-qa.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
