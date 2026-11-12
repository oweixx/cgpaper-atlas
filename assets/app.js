'use strict';
const $ = id => document.getElementById(id);
const fmt = value => Number(value).toLocaleString('en-US');
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeURL = value => /^https?:\/\//i.test(value || '') ? esc(value) : '#';
let papers = [], filtered = [], summary, page = 1, pageSize = 25;
const params = new URLSearchParams(location.search);
let selectedCountry = /^(?:[A-Z]{2}|unknown)$/.test(params.get('country') || '') ? params.get('country') : '';
let countryStatus = 'loading';
const viewFromPath = {'by_year.html':'trends','coauthor_network.html':'research','research_areas.html':'research','global_research.html':'world','dataset_preview.html':'data'};
let view = params.get('view') || viewFromPath[location.pathname.split('/').pop()] || 'explore';
const venues = ['SIGGRAPH','SIGGRAPH Asia','Eurographics','Pacific Graphics','TOG','CGF','TVCG','C&G'];
function selectPapers(chosen,from,to,kind=''){return papers.flatMap(p=>{const v=venues.find(v=>chosen.has(v)&&p.venues.includes(v));if(!v)return [];const year=p.venue_years[v];return year>=from&&year<=to&&(!kind||p.article_kind===kind)?[{...p,year,chart_venue:v}]:[];});}

async function getJSON(url) {
  const r = await fetch(url, {cache:'no-cache'});
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return r.json();
}
function showView(next) {
  if(next === 'network') next = 'research';
  view = ['explore','trends','research','world','data'].includes(next) ? next : 'explore';
  document.querySelectorAll('.view').forEach(el => el.classList.toggle('active', el.id === 'view-' + view));
  document.querySelectorAll('nav a').forEach(el => {el.classList.toggle('active', el.dataset.view === view); if(el.dataset.view === view)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});
  const headings = {explore:['The landscape of computer graphics.','Explore research across eight conferences and journals. Find papers, follow ideas, and discover the people behind them.'],trends:['See how the field evolves.','Publication trends across the collected corpus. Compare venues and years, with source coverage kept in view.'],research:['Follow the ideas shaping graphics.','Explore research areas, detailed topics, and their share of publications over time.'],world:['A world of computer graphics research.','Compare work-time affiliations, unique authors, and research interests across countries and regions.'],data:['Sources you can trace.','Understand the collection, inspect its coverage, and take the data with you.']};
  $('page-title').textContent = headings[view][0]; $('page-subtitle').textContent = headings[view][1];
  const p = new URLSearchParams(location.search); p.set('view', view);
  history.replaceState(null,'','?' + p.toString());
  if (summary && view === 'trends') renderTrends();
  if (papers.length && view === 'research') renderResearch();
  if (papers.length && view === 'world') renderWorld();
}
function renderSummary() {
  $('stat-papers').textContent = fmt(summary.total);
  $('stat-years').textContent = `${summary.min_year}–${summary.max_year}`;
  $('stat-abstracts').textContent = `${(100 * summary.with_abstract / summary.total).toFixed(1)}%`;
  $('stat-citations').textContent = `${(100 * summary.with_citations / summary.total).toFixed(1)}%`;
  $('updated').textContent = 'Updated ' + summary.built_at.slice(0,10);
  $('year-from').value = params.get('from') || summary.min_year;
  $('year-to').value = params.get('to') || summary.max_year;
  for (const id of ['year-from','year-to']) {$(id).min=summary.min_year;$(id).max=summary.max_year;}
  $('venue-filters').innerHTML = venues.map(v => `<label class="venue-option"><input type="checkbox" value="${v}" checked><span class="dot" style="background:${summary.venues[v].color}"></span><span>${v}</span><span class="count">${fmt(summary.venues[v].count)}</span></label>`).join('');
  if(params.has('venue'))document.querySelectorAll('#venue-filters input').forEach(el => el.checked=params.get('venue').split(',').includes(el.value));
  $('topic').innerHTML = '<option value="">All research topics</option>' + summary.topics.map(t=>`<option>${esc(t)}</option>`).join('');
  $('topic').value = params.get('topic') || '';
  $('subtopic').innerHTML = '<option value="">All detailed topics</option>' + summary.subtopics.map(t=>`<option>${esc(t)}</option>`).join('');
  $('subtopic').value = params.get('subtopic') || '';
  $('query').value = params.get('q') || ''; $('article-kind').value=params.get('kind')||'';
  const minimum=params.get('min-citations');
  $('min-citations').value=minimum!==null&&Number.isFinite(Number(minimum))&&Number(minimum)>=0?minimum:'';
  $('sort').value=['newest','citations','oldest','title'].includes(params.get('sort'))?params.get('sort'):'newest';
  $('coverage-body').innerHTML = venues.map(v => {const m=summary.venues[v]; return `<tr><td><b>${v}</b></td><td>${fmt(m.count)}</td><td>${m.min_year}–${m.max_year}</td><td>${(100*m.with_abstract/m.count).toFixed(1)}%</td><td>${(100*m.with_citations/m.count).toFixed(1)}%</td></tr>`;}).join('');
  $('coverage-note').textContent=summary.coverage_note;
  $('topic-note').textContent=summary.topic_note;
  document.querySelectorAll('.citation-note').forEach(el=>el.textContent=summary.citation_note);
}
function paperCountries(p){return Object.keys(geoData?.papers[p.id]?.countries||{}).sort();}
function matchesCountry(p){
  if(!selectedCountry)return true;
  if(countryStatus!=='ready')return false;
  const countries=geoData.papers[p.id]?.countries||{};
  return selectedCountry==='unknown'?!Object.keys(countries).length:Object.hasOwn(countries,selectedCountry);
}
async function loadCountryFilter(){
  countryStatus='loading';$('country').disabled=true;$('country-retry').hidden=true;
  $('country-status').textContent='Loading affiliation countries...';
  if(selectedCountry)$('country').innerHTML=`<option value="${esc(selectedCountry)}">${esc(selectedCountry==='unknown'?'Unknown affiliation':countryName(selectedCountry))}</option>`;
  filterPapers();
  try{
    await loadAffiliations();
    const codes=[...new Set(Object.values(geoData.papers).flatMap(p=>Object.keys(p.countries)))].sort((a,b)=>countryName(a).localeCompare(countryName(b)));
    const unindexed=selectedCountry&&selectedCountry!=='unknown'&&!codes.includes(selectedCountry);
    if(unindexed)codes.push(selectedCountry);
    $('country').innerHTML='<option value="">All countries / regions</option><option value="unknown">Unknown affiliation</option>'+codes.map(c=>`<option value="${c}">${esc(countryName(c))} (${c})${unindexed&&c===selectedCountry?' - no indexed affiliation':''}</option>`).join('');
    $('country').value=selectedCountry;$('country').disabled=false;countryStatus='ready';
    $('country-status').textContent='Includes any author. Unknown: no recorded country for the paper.';
  }catch(e){
    countryStatus='error';$('country-retry').hidden=false;
    $('country-status').textContent='Country data could not be loaded. Retry, or reset all to search without a country.';
  }
  filterPapers();
}
function filterPapers() {
  if (!summary || !papers.length) return;
  const chosen=new Set([...document.querySelectorAll('#venue-filters input:checked')].map(e=>e.value));
  const tokens=$('query').value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  const from=Number($('year-from').value)||summary.min_year, to=Number($('year-to').value)||summary.max_year;
  const minimum=$('min-citations').value === '' ? null : Number($('min-citations').value);
  const topic=$('topic').value, subtopic=$('subtopic').value;
  filtered=selectPapers(chosen,from,to,$('article-kind').value).filter(p=>matchesCountry(p)&&(!topic||p.topics.includes(topic))&&(!subtopic||p.subtopics.includes(subtopic))&&(minimum===null||(p.citation_count!==null&&p.citation_count>=minimum))&&tokens.every(t=>p._search.includes(t)));
  const mode=$('sort').value;
  filtered.sort((a,b)=> mode==='citations' ? (b.citation_count??-1)-(a.citation_count??-1)||b.year-a.year : mode==='oldest' ? a.year-b.year||a.title.localeCompare(b.title) : mode==='title' ? a.title.localeCompare(b.title) : b.year-a.year||(b.citation_count??-1)-(a.citation_count??-1));
  page=1; renderResults(); renderChart(filtered,'mini-chart'); renderCloud();
  $('export-filtered').disabled=!!selectedCountry&&countryStatus!=='ready';
  const state=new URLSearchParams(); state.set('view',view);
  if($('query').value.trim())state.set('q',$('query').value.trim());
  if($('article-kind').value)state.set('kind',$('article-kind').value);if(topic)state.set('topic',topic);if(subtopic)state.set('subtopic',subtopic);
  if(chosen.size!==venues.length)state.set('venue',[...chosen].join(','));
  if(from!==summary.min_year)state.set('from',from);if(to!==summary.max_year)state.set('to',to);
  if(selectedCountry)state.set('country',selectedCountry);
  if(minimum!==null)state.set('min-citations',minimum);
  if(mode!=='newest')state.set('sort',mode);
  history.replaceState(null,'','?'+state);
}
function renderResults() {
  if(selectedCountry&&countryStatus!=='ready'){
    const message=countryStatus==='error'?'Country data unavailable. Retry the country filter or reset all.':'Loading papers for the selected country...';
    $('result-status').textContent=message;$('range-info').textContent='Waiting for country data';
    $('prev').disabled=true;$('next').disabled=true;$('page-info').textContent='Page 1';
    $('paper-body').innerHTML=`<tr><td colspan="4"><div class="empty">${message}</div></td></tr>`;
    return;
  }
  const max=Math.max(1,Math.ceil(filtered.length/pageSize)); page=Math.min(page,max);
  $('result-status').innerHTML=`${fmt(filtered.length)} papers <span>in this view</span>`;
  $('page-info').textContent=`Page ${page} of ${fmt(max)}`;
  $('range-info').textContent=filtered.length ? `${fmt((page-1)*pageSize+1)}–${fmt(Math.min(page*pageSize,filtered.length))} of ${fmt(filtered.length)}` : 'No papers found';
  $('prev').disabled=page<=1; $('next').disabled=page>=max;
  $('paper-body').innerHTML=filtered.slice((page-1)*pageSize,page*pageSize).map(p=>{
    const v=summary.venues[p.venue];
    const names=p.authors.slice(0,5).map(a=>`<button class="author-link" data-author="${esc(a)}">${esc(a)}</button>`).join(', ')+(p.authors.length>5?` +${p.authors.length-5} more`:'');
    return `<tr><td><a class="paper-title" href="${safeURL(p.url)}" target="_blank" rel="noopener noreferrer">${esc(p.title)} <span aria-hidden="true">↗</span></a><div class="authors">${names}</div><div class="paper-meta">${p.topics.slice(0,2).map(t=>`<span class="tag">${esc(t)}</span>`).join('')}${p.pdf_url?`<a class="paper-link" href="${safeURL(p.pdf_url)}" target="_blank" rel="noopener noreferrer">PDF ↗</a>`:''}${p.doi?`<a class="paper-link" href="https://doi.org/${esc(p.doi)}" target="_blank" rel="noopener noreferrer">DOI ↗</a>`:''}</div>${p.abstract?`<details class="abstract"><summary>Read abstract</summary><p>${esc(p.abstract)}</p></details>`:''}</td><td><span class="tag venue-tag" style="color:${v.color};background:${v.color}12">${esc(p.venue)}</span>${p.venues.filter(v=>v!==p.venue).map(v=>`<span class="tag venue-tag">${esc(v)}</span>`).join('')}</td><td class="year-cell" title="${esc(p.year_basis)}${p.publication_year&&p.publication_year!==p.year?'; bibliographic publication year: '+p.publication_year:''}">${p.year}</td><td class="citation">${p.citation_count===null?'N/A':fmt(p.citation_count)}<small>${esc(p.citation_source||'Unavailable')}</small></td></tr>`;
  }).join('') || '<tr><td colspan="4"><div class="empty">No papers match these filters.<br>Try a broader search or reset the filters.</div></td></tr>';
}
function renderChart(rows,id) {
  const target=$(id);if(!rows.length){target.innerHTML='<div class="empty">No publications in this selection.</div>';return;}
  const counts=new Map();rows.forEach(p=>{if(!counts.has(p.year))counts.set(p.year,{});const c=counts.get(p.year);const v=p.chart_venue||p.venue;c[v]=(c[v]||0)+1;});
  const observed=[...counts.keys()].sort((a,b)=>a-b), years=Array.from({length:observed.at(-1)-observed[0]+1},(_,i)=>observed[0]+i);for(const y of years)if(!counts.has(y))counts.set(y,{});const max=Math.max(...years.map(y=>Object.values(counts.get(y)).reduce((a,b)=>a+b,0)));
  const W=900,H=230,L=45,R=10,T=14,B=30,bw=(W-L-R)/years.length;
  const step=Math.max(1,Math.ceil(max/4)),axisMax=Math.ceil(max/step)*step,ticks=axisMax/step;
  let shapes='';for(let i=0;i<=ticks;i++){const y=T+(H-T-B)*i/ticks;shapes+=`<line x1="${L}" y1="${y}" x2="${W-R}" y2="${y}" stroke="#edf1f5"/><text x="${L-8}" y="${y+3}" text-anchor="end" fill="#8795a3" font-size="9">${fmt(axisMax-i*step)}</text>`;}
  years.forEach((year,i)=>{let bottom=H-B;venues.forEach(v=>{const n=counts.get(year)[v]||0,h=n/axisMax*(H-T-B);if(n){shapes+=`<rect x="${L+i*bw+1}" y="${bottom-h}" width="${Math.max(1,bw-3)}" height="${h}" fill="${summary.venues[v].color}" opacity=".82"><title>${v} ${year}: ${fmt(n)} papers</title></rect>`;bottom-=h;}});if(i%Math.max(1,Math.ceil(years.length/12))===0||i===years.length-1)shapes+=`<text x="${L+(i+.5)*bw}" y="${H-9}" text-anchor="middle" fill="#8795a3" font-size="9">${year}</text>`;});
  target.innerHTML=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Unique publication counts by year; conference-first grouping">${shapes}</svg>`;
}
function renderCloud(){const c=new Map();for(const p of filtered)for(const t of p.topics)c.set(t,(c.get(t)||0)+1);$('topic-cloud').innerHTML=[...c].sort((a,b)=>b[1]-a[1]).map(([t,n])=>`<button data-topic="${esc(t)}">${esc(t)} <span style="color:#91a0ae;font-size:10px">${fmt(n)}</span></button>`).join('')||'<span class="filter-note">No topics in this selection.</span>';}
function renderTrends(){renderChart(papers,'trend-chart');const years=Array.from({length:summary.max_year-summary.min_year+1},(_,i)=>summary.max_year-i);$('trends-body').innerHTML=years.map(y=>`<tr><td><b>${y}</b>${y===summary.current_year?' <small>partial</small>':''}</td>${venues.map(v=>`<td title="${esc(summary.venues[v].name)}">${y<summary.venues[v].since?'&mdash;':summary.venues[v].years[y]?fmt(summary.venues[v].years[y]):'<span class="not-held">No indexed papers</span>'}</td>`).join('')}<td><b>${fmt(summary.unique_years[y]||0)}</b></td></tr>`).join('');}
function exportFiltered(){const columns=['venue','venues','year','publication_year','article_kind','title','authors','doi','url','citation_count','citation_source','affiliation_country_codes','affiliation_countries'];const quote=x=>{let s=Array.isArray(x)?x.join('; '):String(x??'');if(/^[\s]*[=+\-@]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';};const content='\ufeff'+[columns.join(','),...filtered.map(p=>columns.map(k=>quote(k==='affiliation_country_codes'?(geoData?paperCountries(p):'Unavailable'):k==='affiliation_countries'?(geoData?(paperCountries(p).map(countryName).join('; ')||'Unknown affiliation'):'Unavailable'):p[k])).join(','))].join('\r\n');const url=URL.createObjectURL(new Blob([content],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='cgpaper_atlas_filtered.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function resetFilters(){document.querySelectorAll('#venue-filters input').forEach(e=>e.checked=true);$('query').value='';$('topic').value='';$('subtopic').value='';$('min-citations').value='';$('article-kind').value='';$('sort').value='newest';selectedCountry='';if(countryStatus==='ready')$('country').value='';else $('country').innerHTML='<option value="">All countries / regions</option>';$('year-from').value=summary.min_year;$('year-to').value=summary.max_year;filterPapers();}
document.querySelectorAll('[data-view]').forEach(el=>el.addEventListener('click',e=>{e.preventDefault();showView(el.dataset.view);}));
document.addEventListener('click',e=>{const a=e.target.closest('[data-author]');if(a){$('query').value=a.dataset.author;showView('explore');filterPapers();}const t=e.target.closest('[data-topic]');if(t){$('topic').value=t.dataset.topic;filterPapers();}});
let searchTimer;$('query').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(filterPapers,180);});
for(const id of ['year-from','year-to','min-citations','topic','subtopic','article-kind','sort','venue-filters'])$(id).addEventListener('change',()=>{if(summary&&papers.length)filterPapers();});
$('country').onchange=()=>{selectedCountry=$('country').value;filterPapers();};
$('country-retry').onclick=loadCountryFilter;
$('reset').onclick=resetFilters;$('export-filtered').onclick=exportFiltered;
$('prev').onclick=()=>{page--;renderResults();};$('next').onclick=()=>{page++;renderResults();};$('page-size').onchange=()=>{pageSize=Number($('page-size').value);page=1;renderResults();};
document.addEventListener('keydown',e=>{if(e.key==='/'&&!['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName)){e.preventDefault();showView('explore');$('query').focus();}});

showView(view);
(async()=>{try{summary=await getJSON('data/summary.json');renderSummary();loadCountryFilter();papers=await getJSON('data/papers.json');for(const p of papers)p._search=[p.title,...p.authors,p.doi,p.abstract].join(' ').toLocaleLowerCase();if(papers.length!==summary.total)throw new Error('Dataset and summary totals differ');document.querySelectorAll('[data-requires-data]').forEach(e=>e.disabled=false);filterPapers();document.querySelectorAll('.chart-legend').forEach(el=>el.innerHTML=venues.map(v=>`<span><i style="background:${summary.venues[v].color}"></i>${v}</span>`).join(''));if(view==='trends')renderTrends();initializeAnalytics();if(view==='research')renderResearch();if(view==='world')renderWorld();}catch(e){$('load-error').hidden=false;$('load-error').textContent='The collection could not be loaded. Serve this folder over HTTP and retry. '+e.message;$('result-status').textContent='Collection unavailable';}})();
