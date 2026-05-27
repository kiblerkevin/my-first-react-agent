const charts = {};

let runsPageSize = 5;
let runsOffset = 0;
let runsTotal = 0;

function formatDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function formatDuration(seconds) {
    if (!seconds) return '—';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

function badgeHtml(status) {
    const cls = {success:'badge-success',failed:'badge-failed',skipped:'badge-skipped',running:'badge-running'}[status] || '';
    return `<span class="inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${cls}">${status}</span>`;
}

async function fetchJson(url) {
    const res = await fetch(url);
    return res.json();
}

function initRunsControls() {
    document.getElementById('runs-toggle').addEventListener('click', () => {
        const content = document.getElementById('runs-content');
        const chevron = document.getElementById('runs-chevron');
        const hidden = content.classList.toggle('hidden');
        chevron.style.transform = hidden ? 'rotate(-90deg)' : '';
    });

    document.getElementById('runs-page-size').addEventListener('change', (e) => {
        runsPageSize = parseInt(e.target.value);
        runsOffset = 0;
        loadRuns();
    });

    document.getElementById('runs-prev').addEventListener('click', () => {
        if (runsOffset > 0) {
            runsOffset = Math.max(0, runsOffset - runsPageSize);
            loadRuns();
        }
    });

    document.getElementById('runs-next').addEventListener('click', () => {
        if (runsOffset + runsPageSize < runsTotal) {
            runsOffset += runsPageSize;
            loadRuns();
        }
    });
}

async function loadQuickStats() {
    const runs = await fetchJson('/dashboard/api/runs');
    const approvals = await fetchJson('/dashboard/api/approvals');
    const cache = await fetchJson('/dashboard/api/cache');

    const successRuns = runs.filter(r => r.status === 'success');
    const avgScore = successRuns.length > 0
        ? (successRuns.reduce((s, r) => s + (r.overall_score || 0), 0) / successRuns.length).toFixed(1)
        : '—';

    document.getElementById('quick-stats').innerHTML = `
        <div class="text-center p-4 bg-gray-50 rounded-lg"><div class="text-3xl font-bold text-[#1a1a2e]">${runs.length}</div><div class="text-xs text-gray-500 mt-1">Runs (30 days)</div></div>
        <div class="text-center p-4 bg-gray-50 rounded-lg"><div class="text-3xl font-bold text-[#1a1a2e]">${avgScore}</div><div class="text-xs text-gray-500 mt-1">Avg Score</div></div>
        <div class="text-center p-4 bg-gray-50 rounded-lg"><div class="text-3xl font-bold text-[#1a1a2e]">${approvals.approved || 0}</div><div class="text-xs text-gray-500 mt-1">Approved</div></div>
        <div class="text-center p-4 bg-gray-50 rounded-lg"><div class="text-3xl font-bold text-[#1a1a2e]">${cache.hit_rate || 0}%</div><div class="text-xs text-gray-500 mt-1">Cache Hit Rate</div></div>
    `;
}

async function loadRuns() {
    const data = await fetchJson(`/dashboard/api/runs/window?offset=${runsOffset}&limit=${runsPageSize}`);
    runsTotal = data.total;
    const runs = data.runs;

    const currentPage = Math.floor(runsOffset / runsPageSize) + 1;
    const totalPages = Math.ceil(runsTotal / runsPageSize);

    document.getElementById('runs-page-indicator').textContent = `Page ${currentPage} of ${totalPages}`;
    document.getElementById('runs-prev').disabled = runsOffset === 0;
    document.getElementById('runs-next').disabled = runsOffset + runsPageSize >= runsTotal;

    const tbody = document.querySelector('#runs-table tbody');
    tbody.innerHTML = runs.map(r => `
        <tr>
            <td class="p-2 border-b border-gray-100">${formatDate(r.started_at)}</td>
            <td class="p-2 border-b border-gray-100">${badgeHtml(r.status)}</td>
            <td class="p-2 border-b border-gray-100">${formatDuration(r.duration_seconds)}</td>
            <td class="p-2 border-b border-gray-100">${r.overall_score ? r.overall_score + '/10' : '—'}</td>
            <td class="p-2 border-b border-gray-100">${r.articles_new ?? '—'} new / ${r.articles_fetched ?? '—'} total</td>
            <td class="p-2 border-b border-gray-100">${r.summaries_count ?? '—'}</td>
            <td class="p-2 border-b border-gray-100">${r.draft_attempts ?? '—'} drafts / ${r.revision_tool_calls ?? '—'} calls</td>
            <td class="p-2 border-b border-gray-100">${r.publish_success === true ? '✅' : r.publish_success === false ? '❌' : '—'}</td>
        </tr>
    `).join('');
}

async function loadEvalChart() {
    const data = await fetchJson('/dashboard/api/evaluations');
    if (charts.eval) charts.eval.destroy();

    charts.eval = new Chart(document.getElementById('eval-chart'), {
        type: 'line',
        data: {
            labels: data.map(d => d.date),
            datasets: ['accuracy','completeness','readability','seo'].map((c, i) => ({
                label: c,
                data: data.map(d => d[c] || null),
                borderColor: ['#28a745','#007bff','#ffc107','#dc3545'][i],
                tension: 0.3,
                fill: false
            }))
        },
        options: { responsive: true, maintainAspectRatio: false, scales: { y: { min: 0, max: 10 } } }
    });
}

function renderLlmCard(title, llm) {
    const count = llm.generation_count || 0;
    let html = `<div class="bg-white rounded-lg p-5 shadow-sm">
        <h2 class="text-sm font-medium text-gray-500 mb-4 pb-2 border-b border-gray-100">${title}</h2>
        <div class="flex justify-between py-1.5 border-b border-gray-50"><span class="text-gray-500">Generations</span><span class="font-semibold">${count.toLocaleString()}</span></div>
        <div class="flex justify-between py-1.5 border-b border-gray-50"><span class="text-gray-500">Input Tokens</span><span class="font-semibold">${(llm.total_input_tokens || 0).toLocaleString()}</span></div>
        <div class="flex justify-between py-1.5 border-b border-gray-50"><span class="text-gray-500">Output Tokens</span><span class="font-semibold">${(llm.total_output_tokens || 0).toLocaleString()}</span></div>
        <div class="flex justify-between py-1.5"><span class="text-gray-500">Total Cost</span><span class="font-semibold">$${(llm.total_cost || 0).toFixed(4)}</span></div>`;

    if (llm.by_model && Object.keys(llm.by_model).length > 0) {
        html += `<div class="mt-3 pt-2 border-t border-gray-100"><div class="text-xs font-medium text-gray-400 mb-1">By Model</div>`;
        for (const [model, usage] of Object.entries(llm.by_model)) {
            html += `<div class="flex justify-between py-1 text-xs"><span class="text-gray-500 truncate mr-2">${model}</span><span class="font-semibold whitespace-nowrap">${usage.input.toLocaleString()} / ${usage.output.toLocaleString()} tok</span></div>`;
        }
        html += `</div>`;
    }

    if (llm.by_function && Object.keys(llm.by_function).length > 0) {
        html += `<div class="mt-3 pt-2 border-t border-gray-100"><div class="text-xs font-medium text-gray-400 mb-1">By Function</div>`;
        for (const [func, usage] of Object.entries(llm.by_function)) {
            html += `<div class="flex justify-between py-1 text-xs"><span class="text-gray-500 truncate mr-2">${func}</span><span class="font-semibold whitespace-nowrap">${usage.input.toLocaleString()} / ${usage.output.toLocaleString()} tok</span></div>`;
        }
        html += `</div>`;
    }

    if (!count) {
        html += `<div class="text-gray-400 text-xs mt-2">No LLM usage data found.</div>`;
    }
    html += `</div>`;
    return html;
}

async function loadApiSection() {
    const [health, llm, llmPrev, llmAvg] = await Promise.all([
        fetchJson('/dashboard/api/health'),
        fetchJson('/dashboard/api/llm'),
        fetchJson('/dashboard/api/llm/previous-run'),
        fetchJson('/dashboard/api/llm/weekly-avg'),
    ]);
    const section = document.getElementById('api-section');

    Object.keys(charts).filter(k => k.startsWith('api-')).forEach(k => { charts[k].destroy(); delete charts[k]; });

    const sources = ['espn', 'newsapi', 'serpapi'];
    const sourceLabels = { espn: 'ESPN', newsapi: 'NewsAPI', serpapi: 'SerpAPI' };
    let html = '';
    sources.forEach(src => {
        const d = health.find(h => h.source === src) || { success: 0, error: 0, total_articles: 0 };
        html += `<div class="bg-white rounded-lg p-5 shadow-sm">
            <h2 class="text-sm font-medium text-gray-500 mb-4 pb-2 border-b border-gray-100">${sourceLabels[src] || src}</h2>
            <div class="relative h-[180px]"><canvas id="api-${src}"></canvas></div>
            <div class="flex justify-between py-1.5 mt-2"><span class="text-gray-500">Total Articles</span><span class="font-semibold">${d.total_articles || 0}</span></div>
        </div>`;
    });

    html += renderLlmCard('🤖 Previous Run LLM', llmPrev);
    html += renderLlmCard('🤖 7-Run Avg LLM', llmAvg);
    html += renderLlmCard('🤖 LLM Usage (30 days)', llm);
    section.innerHTML = html;

    sources.forEach(src => {
        const d = health.find(h => h.source === src) || { success: 0, error: 0 };
        charts[`api-${src}`] = new Chart(document.getElementById(`api-${src}`), {
            type: 'pie',
            data: { labels: ['Success','Error'], datasets: [{ data: [d.success||0, d.error||0], backgroundColor: ['#28a745','#dc3545'] }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
        });
    });
}

async function loadApprovalChart() {
    const data = await fetchJson('/dashboard/api/approvals');
    if (charts.approval) charts.approval.destroy();

    charts.approval = new Chart(document.getElementById('approval-chart'), {
        type: 'doughnut',
        data: {
            labels: ['Approved','Rejected','Expired','Pending'],
            datasets: [{ data: [data.approved||0, data.rejected||0, data.expired||0, data.pending||0], backgroundColor: ['#28a745','#dc3545','#6c757d','#ffc107'] }]
        },
        options: { responsive: true, maintainAspectRatio: false }
    });
}

async function loadTeamList() {
    const data = await fetchJson('/dashboard/api/teams');
    const teams = Object.keys(data).sort((a, b) => data[b] - data[a]);
    document.getElementById('team-list').innerHTML = teams.map(t =>
        `<div class="flex justify-between py-1.5 border-b border-gray-50 last:border-b-0"><span class="text-gray-500">${t}</span><span class="font-semibold">${data[t]}</span></div>`
    ).join('');
}

async function loadSourceChart() {
    const data = await fetchJson('/dashboard/api/sources');
    if (charts.source) charts.source.destroy();

    charts.source = new Chart(document.getElementById('source-chart'), {
        type: 'pie',
        data: { labels: Object.keys(data), datasets: [{ data: Object.values(data), backgroundColor: ['#007bff','#ffc107','#28a745','#dc3545'] }] },
        options: { responsive: true, maintainAspectRatio: false }
    });
}

async function loadCacheStats() {
    const data = await fetchJson('/dashboard/api/cache');
    document.getElementById('cache-stats').innerHTML = `
        <div class="flex justify-between py-1.5 border-b border-gray-50"><span class="text-gray-500">Total Summarizations</span><span class="font-semibold">${data.total}</span></div>
        <div class="flex justify-between py-1.5 border-b border-gray-50"><span class="text-gray-500">Cache Hits</span><span class="font-semibold">${data.cache_hits}</span></div>
        <div class="flex justify-between py-1.5 border-b border-gray-50"><span class="text-gray-500">Cache Misses</span><span class="font-semibold">${data.cache_misses}</span></div>
        <div class="flex justify-between py-1.5"><span class="text-gray-500">Hit Rate</span><span class="font-semibold">${data.hit_rate}%</span></div>
    `;
}

async function loadAll() {
    document.getElementById('last-updated').textContent = new Date().toLocaleTimeString();
    await Promise.all([
        loadQuickStats(), loadRuns(), loadEvalChart(), loadApiSection(),
        loadApprovalChart(), loadTeamList(), loadSourceChart(), loadCacheStats()
    ]);
}

initRunsControls();
loadAll();
setInterval(loadAll, 5 * 60 * 1000);
