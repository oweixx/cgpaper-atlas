'use strict';
// Evidence is fetched only when a reader opens a paper's explanation.
const topicEvidenceRequests = new Map();
async function topicEvidenceFor(id) {
  if (!/^[a-f0-9]{20}$/.test(id)) throw new Error('Invalid publication ID');
  const prefix = id[0];
  if (!topicEvidenceRequests.has(prefix)) {
    const request = getJSON(`data/topic_evidence/${prefix}.json`).catch(error => {
      topicEvidenceRequests.delete(prefix);
      throw error;
    });
    topicEvidenceRequests.set(prefix, request);
  }
  const entry = (await topicEvidenceRequests.get(prefix))[id];
  if (!entry) throw new Error('Classification evidence is missing');
  return entry;
}
function renderTopicEvidence(entry) {
  const groups = new Map();
  for (const evidence of entry.evidence) {
    const key = `${evidence.area} / ${evidence.subtopic}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(evidence);
  }
  const sections = [...groups].map(([label, evidence]) => {
    const items = evidence.map(e => {
      if (e.basis === 'openalex_keyword') {
        return `<li><a href="${safeURL(e.source_url)}" target="_blank" rel="noopener noreferrer">OpenAlex keyword</a>: <b>${esc(e.terms.join(', '))}</b> <span class="evidence-source">(source score ${esc(e.source_score.toFixed(3))}, rank ${esc(e.source_rank)})</span></li>`;
      }
      return `<li><b>${e.basis === 'title' ? 'Title' : 'Abstract'} match:</b> ${esc(e.terms.join(', '))}<blockquote>${esc(e.snippet)}</blockquote></li>`;
    }).join('');
    return `<section><h4>${esc(label)}</h4><ul>${items}</ul></section>`;
  }).join('');
  const empty = '<p>No sufficiently specific evidence was found. This paper stays in Other / Unclassified; this does not mean it is outside computer graphics.</p>';
  const source = entry.openalex_id ? ` · <a href="${safeURL(entry.openalex_id)}" target="_blank" rel="noopener noreferrer">OpenAlex work</a> · retrieved ${esc((entry.retrieved_at || '').slice(0, 10))}` : '';
  return `<p class="evidence-method">Automatic classification · ${esc(entry.version)}${source}</p>${sections || empty}<p class="evidence-limit">OpenAlex keywords are model predictions. Their source scores measure keyword relevance, not the accuracy of these CG labels. Title and abstract excerpts are normalized for matching. Labels can overlap and can be wrong.${entry.abstract_available ? '' : ' No abstract was available for local matching.'}</p>`;
}
async function showTopicEvidence(details) {
  if (details.dataset.loaded || details.dataset.loading) return;
  const body = details.querySelector('.topic-evidence-body');
  details.dataset.loading = 'true';
  body.textContent = 'Loading classification evidence…';
  try {
    body.innerHTML = renderTopicEvidence(await topicEvidenceFor(details.dataset.paperId));
    details.dataset.loaded = 'true';
  } catch (_) {
    body.innerHTML = '<p>Classification evidence could not be loaded.</p><button type="button" class="text-button" data-retry-evidence>Retry evidence</button>';
  } finally {
    delete details.dataset.loading;
  }
}
document.addEventListener('toggle', event => {
  if (event.target.matches('details.topic-evidence') && event.target.open) showTopicEvidence(event.target);
}, true);
document.addEventListener('click', event => {
  const retry = event.target.closest('[data-retry-evidence]');
  if (retry) showTopicEvidence(retry.closest('details.topic-evidence'));
});
