const LIMIT = 7;
const FLOORS = {accuracy: 8.0, completeness: 7.0, readability: 7.0, seo: 6.0};
let currentOffset = 0;
let totalRuns = 0;
let currentRuns = [];

function formatDate(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function scoreBadge(criterion, score) {
    const floor = FLOORS[criterion] || 0;
    const cls = score >= floor
        ? 'bg-green-100 text-green-800'
        : 'bg-red-100 text-red-800';
    return `<span class="px-2 py-0.5 rounded text-xs font-semibold ${cls}">${criterion}: ${score}</span>`;
}

function toggleRun(runId) {
    const body = document.getElementById(`run-body-${runId}`);
    if (body.classList.contains('hidden')) {
        body.classList.remove('hidden');
        if (!body.dataset.loaded) loadIterations(runId, body);
    } else {
        body.classList.add('hidden');
    }
}

function toggleIteration(id) {
    document.getElementById(`iter-body-${id}`).classList.toggle('hidden');
}

function toggleDraft(id) {
    document.getElementById(`draft-frame-${id}`).classList.toggle('hidden');
}

async function loadIterations(runId, container) {
    container.innerHTML = '<p class="p-3 text-gray-400">Loading iterations...</p>';
    try {
        const res = await fetch(`/dashboard/api/iterations/${encodeURIComponent(runId)}`);
        const data = await res.json();

        if (!data.iterations || data.iterations.length === 0) {
            container.innerHTML = '<p class="p-3 text-gray-400">No iteration data available for this run.</p>';
            container.dataset.loaded = 'true';
            return;
        }

        let html = '';
        if (data.score_progression && data.score_progression.length > 1) {
            const max = Math.max(...data.score_progression, 10);
            html += '<div class="p-3"><strong class="text-sm">Score Progression:</strong> <div class="inline-flex items-end gap-0.5 ml-2 h-8">';
            data.score_progression.forEach((s, i) => {
                const h = Math.max(3, (s / max) * 30);
                html += `<div class="w-5 bg-blue-500 rounded-t" style="height:${h}px;" title="Attempt ${i+1}: ${s}"></div>`;
            });
            html += '</div></div>';
        }

        data.iterations.forEach((iter, idx) => {
            const iterId = `${runId}-${idx}`;
            const eval_ = iter.evaluation;
            const draft = iter.draft;
            const overallScore = eval_ ? eval_.overall_score : '—';

            let badges = '';
            if (eval_ && eval_.criteria_scores) {
                Object.entries(eval_.criteria_scores).forEach(([k, v]) => { badges += scoreBadge(k, v); });
            }

            html += `<div class="border border-gray-200 rounded-md mt-4 overflow-hidden">`;
            html += `<div class="px-4 py-3 bg-gray-50 flex justify-between items-center cursor-pointer hover:bg-blue-50" onclick="toggleIteration('${iterId}')">`;
            html += `<h4 class="text-sm font-medium">Attempt ${iter.attempt} — Overall: ${overallScore}/10</h4>`;
            html += `<div class="flex gap-2">${badges}</div>`;
            html += `</div>`;
            html += `<div class="hidden p-4" id="iter-body-${iterId}">`;

            if (eval_ && eval_.criteria_scores) {
                html += `<table class="w-full text-sm mb-4">`;
                html += `<thead><tr><th class="text-left p-2 bg-gray-50 border-b-2 border-gray-200">Criterion</th><th class="text-left p-2 bg-gray-50 border-b-2 border-gray-200">Score</th><th class="text-left p-2 bg-gray-50 border-b-2 border-gray-200">Floor</th><th class="text-left p-2 bg-gray-50 border-b-2 border-gray-200">Status</th><th class="text-left p-2 bg-gray-50 border-b-2 border-gray-200">Reasoning</th></tr></thead><tbody>`;
                Object.entries(eval_.criteria_scores).forEach(([criterion, score]) => {
                    const floor = FLOORS[criterion] || '—';
                    const status = score >= floor ? '✅' : '❌';
                    const reasoning = (eval_.criteria_reasoning && eval_.criteria_reasoning[criterion]) || '';
                    html += `<tr>
                        <td class="p-2 border-b border-gray-100 font-medium">${criterion}</td>
                        <td class="p-2 border-b border-gray-100">${score}/10</td>
                        <td class="p-2 border-b border-gray-100">${floor}</td>
                        <td class="p-2 border-b border-gray-100">${status}</td>
                        <td class="p-2 border-b border-gray-100 text-gray-500 text-xs max-w-lg">${reasoning}</td>
                    </tr>`;
                });
                html += `</tbody></table>`;
            } else {
                html += `<p class="text-gray-400">No evaluation data for this attempt.</p>`;
            }

            if (draft && draft.content) {
                html += `<div class="border border-gray-300 rounded mt-3">`;
                html += `<div class="px-4 py-3 bg-gray-50 cursor-pointer text-sm font-semibold hover:bg-blue-50 border-b border-gray-300" onclick="toggleDraft('${iterId}')">📄 Toggle Draft Preview — ${draft.title || 'Untitled'}</div>`;
                html += `<iframe class="hidden w-full h-[500px] border-none" id="draft-frame-${iterId}" sandbox="allow-same-origin"></iframe>`;
                html += `</div>`;
                html += `<script>
                    (function() {
                        const frame = document.getElementById('draft-frame-${iterId}');
                        const observer = new MutationObserver(function() {
                            if (!frame.classList.contains('hidden') && !frame.dataset.loaded) {
                                frame.dataset.loaded = 'true';
                                const doc = frame.contentDocument || frame.contentWindow.document;
                                doc.open();
                                doc.write(${JSON.stringify(draft.content)});
                                doc.close();
                            }
                        });
                        observer.observe(frame, { attributes: true, attributeFilter: ['class'] });
                    })();
                <\/script>`;
            } else {
                html += `<p class="text-gray-400 mt-3">No draft content available for this attempt.</p>`;
            }

            html += `</div></div>`;
        });

        container.innerHTML = html;
        container.dataset.loaded = 'true';
    } catch (e) {
        container.innerHTML = `<p class="p-3 text-red-600">Error loading iterations: ${e.message}</p>`;
    }
}

function renderRuns(runs) {
    const container = document.getElementById('runs-container');
    if (!runs || runs.length === 0) {
        container.innerHTML = '<div class="text-center py-10 text-gray-400">No workflow runs found for this window.</div>';
        return;
    }

    let html = '';
    runs.forEach(r => {
        const badgeCls = r.status === 'success' ? 'badge-success' : 'badge-failed';
        html += `<div class="bg-white rounded-lg mb-5 shadow-sm overflow-hidden">`;
        html += `<div class="px-5 py-4 border-b border-gray-100 flex justify-between items-center cursor-pointer hover:bg-gray-50" onclick="toggleRun('${r.run_id}')">`;
        html += `<h3 class="text-sm font-medium">${formatDate(r.started_at)}</h3>`;
        html += `<div class="flex gap-4 text-sm text-gray-500">`;
        html += `<span class="inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${badgeCls}">${r.status}</span>`;
        html += `<span>Score: ${r.overall_score || '—'}/10</span>`;
        html += `<span>Drafts: ${r.draft_attempts || '—'}</span>`;
        html += `</div></div>`;
        html += `<div class="hidden px-5 pb-5" id="run-body-${r.run_id}"></div>`;
        html += `</div>`;
    });
    container.innerHTML = html;
}

async function loadByWindow() {
    const res = await fetch(`/dashboard/api/runs/window?offset=${currentOffset}&limit=${LIMIT}`);
    const data = await res.json();
    totalRuns = data.total;
    currentRuns = data.runs;
    renderRuns(currentRuns);
    updatePageInfo();
}

async function loadByRange() {
    const start = document.getElementById('date-start').value;
    const end = document.getElementById('date-end').value;
    if (!start || !end) return;
    const res = await fetch(`/dashboard/api/runs/range?start=${start}T00:00:00&end=${end}T23:59:59`);
    const data = await res.json();
    currentRuns = data.runs;
    renderRuns(currentRuns);
    document.getElementById('page-info').textContent = `${currentRuns.length} runs in range`;
    document.getElementById('btn-prev').disabled = true;
    document.getElementById('btn-next').disabled = true;
}

function pagePrev() {
    if (currentOffset > 0) {
        currentOffset = Math.max(0, currentOffset - LIMIT);
        loadByWindow();
    }
}

function pageNext() {
    if (currentOffset + LIMIT < totalRuns) {
        currentOffset += LIMIT;
        loadByWindow();
    }
}

function updatePageInfo() {
    const start = currentOffset + 1;
    const end = Math.min(currentOffset + LIMIT, totalRuns);
    document.getElementById('page-info').textContent = `${start}–${end} of ${totalRuns}`;
    document.getElementById('btn-prev').disabled = currentOffset === 0;
    document.getElementById('btn-next').disabled = currentOffset + LIMIT >= totalRuns;
}

// Set default date range
const today = new Date();
const weekAgo = new Date(today);
weekAgo.setDate(weekAgo.getDate() - 7);
document.getElementById('date-end').value = today.toISOString().split('T')[0];
document.getElementById('date-start').value = weekAgo.toISOString().split('T')[0];

loadByWindow();
