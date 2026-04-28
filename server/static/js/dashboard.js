const charts = {};

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
    const runs = await fetchJson('/dashboard/api/runs');
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

async function loadApiSection() {
    const [health, llm] = await Promise.all([fetchJson('/dashboard/api/health'), fetchJson('/dashboard/api/llm')]);
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

    const tracked = llm.runs_tracked || 0;
    html += `<div class="bg-white rounded-lg p-5 shadow-sm">
        <h2 class="text-sm font-medium text-gray-500 mb-4 pb-2 border-b border-gray-100">🤖 LLM Usage</h2>
        <div class="flex justify-between py-1.5 border-b border-gray-50"><span class="text-gray-500">Runs Tracked</span><span class="font-semibold">${tracked}</span></div>
        <div class="flex justify-between py-1.5 border-b border-gray-50"><span class="text-gray-500">Input Tokens</span><span class="font-semibold">${llm.total_input_tokens.toLocaleString()}</span></div>
        <div class="flex justify-between py-1.5 border-b border-gray-50"><span class="text-gray-500">Output Tokens</span><span class="font-semibold">${llm.total_output_tokens.toLocaleString()}</span></div>
        <div class="flex justify-between py-1.5"><span class="text-gray-500">Est. Cost</span><span class="font-semibold">$${llm.estimated_cost.toFixed(4)}</span></div>
        ${!tracked ? '<div class="text-gray-400 text-xs mt-2">Token tracking not yet populated.</div>' : ''}
    </div>`;
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

loadAll();
setInterval(loadAll, 5 * 60 * 1000);
