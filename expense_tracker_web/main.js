const DEFAULT_RULES = {
  Groceries: [
    /\btrader\s*joe'?s?\b/i,
    /\bsafeway\b/i,
    /\bwhole\s*foods\b/i,
    /\bcostco\b/i,
    /\bheb\b/i,
    /\bwalmart\b/i,
    /\btarget\b/i,
    /\binstacart\b/i,
  ],
  Restaurants: [
    /\bubereats\b/i,
    /\bdoordash\b/i,
    /\bgrubhub\b/i,
    /\bstarbucks\b/i,
    /\bmcdonald'?s?\b/i,
    /\bchipotle\b/i,
    /\btaco\s*bell\b/i,
    /\bsubway\b/i,
    /\bpizza\b/i,
    /\bkfc\b/i,
    /\bpanda\s*express\b/i,
  ],
  Transport: [
    /\buber\b/i,
    /\blyft\b/i,
    /\bchevron\b/i,
    /\bshell\b/i,
    /\bexxon\b/i,
    /\bbp\b/i,
    /\btesla\b/i,
    /\bvalero\b/i,
    /\bstation\s*gas\b/i,
    /\bgas\b/i,
    /\bmetro\b/i,
    /\bsubway\s*station\b/i,
  ],
  Housing: [
    /\brent\b/i,
    /\bmortgage\b/i,
    /\blandlord\b/i,
    /\bapartment\b/i,
    /\bproperty\s*management\b/i,
    /\bhoa\b/i,
  ],
  Utilities: [
    /\belectric\b/i,
    /\bwater\b/i,
    /\bgas\b/i,
    /\binternet\b/i,
    /\bcomcast\b/i,
    /\bat&t\b/i,
    /\bverizon\b/i,
    /\bt-mobile\b/i,
    /\bspectrum\b/i,
  ],
  Entertainment: [
    /\bnetflix\b/i,
    /\bspotify\b/i,
    /\bhulu\b/i,
    /\bdisney\+?\b/i,
    /\bprime\s*video\b/i,
    /\bxbox\b/i,
    /\bplaystation\b/i,
    /\bsteam\b/i,
  ],
  Shopping: [
    /\bamzn|amazon\b/i,
    /\bebay\b/i,
    /\betsy\b/i,
    /\bbest\s*buy\b/i,
    /\bapple\s*store\b/i,
  ],
  Health: [
    /\bcvs\b/i,
    /\bwalgreens\b/i,
    /\bpharmacy\b/i,
    /\bdoctor\b/i,
    /\bdentist\b/i,
    /\bclinic\b/i,
    /\boptical\b/i,
  ],
  Travel: [
    /\bairbnb\b/i,
    /\bbooking\.com\b/i,
    /\bexpedia\b/i,
    /\bmarriott\b/i,
    /\bhilton\b/i,
    /\bdelta\b/i,
    /\bamerican\s*airlines\b/i,
    /\bsouthwest\b/i,
    /\bunited\b/i,
  ],
  Income: [
    /\bpayroll\b/i,
    /\bsalary\b/i,
    /\bpaycheck\b/i,
    /\bdirect\s*deposit\b/i,
    /\bvenmo\s*cashout\b/i,
    /\bcash\s*app\s*cashout\b/i,
    /\bzelle\s*in\b/i,
    /\binterest\s*payment\b/i,
  ],
  Fees: [
    /\boverdraft\b/i,
    /\bmaintenance\s*fee\b/i,
    /\bservice\s*charge\b/i,
    /\batm\s*fee\b/i,
    /\bwire\s*fee\b/i,
  ],
};

const STORAGE_KEYS = {
  RULES: 'expense_rules',
  TRAIN: 'expense_training',
  LAST_CSV: 'expense_last_csv'
};

function normalizeText(text) {
  if (!text) return '';
  return String(text).normalize('NFKD').replace(/[^\x00-\x7F]/g, '').toLowerCase().trim().replace(/\s+/g, ' ');
}

function extractMerchant(description) {
  const t = normalizeText(description).replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim();
  const tokens = t.split(' ');
  const skip = new Set(['purchase','pos','debit','credit','payment','card','visa','mastercard','amzn','amazon']);
  const filtered = tokens.filter(x => !skip.has(x));
  const merchant = filtered.slice(0, 2).join(' ') || (tokens[0] || '');
  return merchant.trim();
}

function loadRules() {
  const saved = localStorage.getItem(STORAGE_KEYS.RULES);
  let rules = JSON.parse(saved || 'null');
  if (!rules) rules = DEFAULT_RULES;
  // Convert regex strings back to RegExp if needed
  for (const [cat, arr] of Object.entries(rules)) {
    rules[cat] = arr.map(p => {
      if (p instanceof RegExp) return p;
      if (typeof p === 'string') {
        const m = p.match(/^\/(.*)\/(.*)$/);
        if (m) return new RegExp(m[1], m[2]);
        return new RegExp(p, 'i');
      }
      return p;
    });
  }
  return rules;
}

function saveRules(rules) {
  // Serialize regex to string form /pattern/flags
  const obj = {};
  for (const [cat, arr] of Object.entries(rules)) {
    obj[cat] = arr.map(r => r instanceof RegExp ? `/${r.source}/${r.flags}` : String(r));
  }
  localStorage.setItem(STORAGE_KEYS.RULES, JSON.stringify(obj));
}

function rulesCategorize(text, rules) {
  const t = normalizeText(text);
  for (const [cat, arr] of Object.entries(rules)) {
    for (const rx of arr) {
      try { if (rx.test(t)) return cat; } catch (e) {}
    }
  }
  return null;
}

function parseCSV(file) {
  return new Promise((resolve, reject) => {
    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: res => resolve(res.data),
      error: err => reject(err)
    });
  });
}

function canonicalize(rows) {
  const lower = (s) => (s || '').toLowerCase();
  const dateKeys = ['date','transaction date','posted date','posting date','trans date','value date'];
  const descKeys = ['description','details','payee','memo','narrative'];
  const amtKeys = ['amount','transaction amount','value'];
  const debitKeys = ['debit','withdrawal'];
  const creditKeys = ['credit','deposit'];
  const typeKeys = ['type','transaction type'];
  const accountKeys = ['account name','account','account number','card number'];
  const categoryKeys = ['category','categorization'];

  const cols = rows.length ? Object.keys(rows[0]) : [];
  const mapPick = (cands) => cols.find(c => cands.includes(lower(c)));

  const dateCol = mapPick(dateKeys);
  const descCol = mapPick(descKeys);
  const amtCol = mapPick(amtKeys);
  const debitCol = mapPick(debitKeys);
  const creditCol = mapPick(creditKeys);
  const typeCol = mapPick(typeKeys);
  const accountCol = mapPick(accountKeys);
  const categoryCol = mapPick(categoryKeys);

  const out = rows.map(r => {
    let date = r[dateCol] || '';
    let description = r[descCol] || '';
    let amount = r[amtCol];
    let type = r[typeCol] || '';
    let account = r[accountCol] || '';
    let category = r[categoryCol] || '';

    if (amount == null || amount === '') {
      const debit = parseFloat(r[debitCol] || '0');
      const credit = parseFloat(r[creditCol] || '0');
      amount = (credit || 0) - (debit || 0);
    } else {
      amount = parseFloat(String(amount).replace(/,/g, ''));
    }

    // Sign normalization heuristic
    const t = String(type).toLowerCase();
    if (['debit','withdraw','purchase'].some(k => t.includes(k))) amount = -Math.abs(amount);
    if (['credit','deposit','income','refund'].some(k => t.includes(k))) amount = Math.abs(amount);

    const merchant = extractMerchant(description);

    return { date, description, merchant, amount: isFinite(amount) ? amount : 0, category: category || null, type, account };
  });

  return out;
}

// Simple multinomial Naive Bayes for text classification
class NaiveBayes {
  constructor() {
    this.classCounts = {}; // category -> count
    this.tokenCounts = {}; // category -> token -> count
    this.vocab = new Set();
    this.totalDocs = 0;
  }
  tokenize(text) {
    const t = normalizeText(text).replace(/[^a-z0-9\s]/g, ' ');
    const tokens = t.split(/\s+/).filter(Boolean);
    return tokens;
  }
  fit(texts, labels) {
    for (let i = 0; i < texts.length; i++) {
      const y = labels[i];
      if (!y) continue;
      this.totalDocs++;
      this.classCounts[y] = (this.classCounts[y] || 0) + 1;
      const tokens = this.tokenize(texts[i]);
      if (!this.tokenCounts[y]) this.tokenCounts[y] = {};
      for (const tok of tokens) {
        this.vocab.add(tok);
        this.tokenCounts[y][tok] = (this.tokenCounts[y][tok] || 0) + 1;
      }
    }
  }
  predictOne(text) {
    const tokens = this.tokenize(text);
    const vocabSize = this.vocab.size || 1;
    let bestCat = null;
    let bestScore = -Infinity;
    const categories = Object.keys(this.classCounts);
    for (const cat of categories) {
      const prior = Math.log((this.classCounts[cat] || 1) / (this.totalDocs || 1));
      const counts = this.tokenCounts[cat] || {};
      const totalTokens = Object.values(counts).reduce((a,b) => a + b, 0) + vocabSize; // Laplace
      let score = prior;
      for (const tok of tokens) {
        const c = (counts[tok] || 0) + 1;
        score += Math.log(c / totalTokens);
      }
      if (score > bestScore) { bestScore = score; bestCat = cat; }
    }
    return bestCat;
  }
  predict(texts) { return texts.map(t => this.predictOne(t)); }
}

function computeKpis(rows) {
  const expenses = rows.filter(r => r.amount < 0).reduce((s, r) => s + r.amount, 0);
  const income = rows.filter(r => r.amount > 0).reduce((s, r) => s + r.amount, 0);
  const net = income + expenses;
  return { expenses, income, net };
}

function groupByCategory(rows) {
  const map = new Map();
  for (const r of rows) {
    if (r.amount >= 0) continue;
    const cat = r.category || 'Uncategorized';
    map.set(cat, (map.get(cat) || 0) + Math.abs(r.amount));
  }
  const arr = Array.from(map.entries()).map(([Category, Spend]) => ({ Category, Spend }));
  arr.sort((a,b) => b.Spend - a.Spend);
  return arr;
}

function groupByMonth(rows) {
  const map = new Map();
  for (const r of rows) {
    const month = (r.date ? new Date(r.date) : new Date()).toISOString().slice(0,7);
    if (!map.has(month)) map.set(month, { Spend: 0, Income: 0 });
    if (r.amount < 0) map.get(month).Spend += -r.amount; else map.get(month).Income += r.amount;
  }
  const out = Array.from(map.entries()).map(([Month, v]) => ({ Month, ...v }));
  out.sort((a,b) => a.Month.localeCompare(b.Month));
  return out;
}

function fmt(n) { return `$${(n||0).toFixed(2)}`; }

let state = {
  rows: [],
  filtered: [],
  rules: loadRules(),
  model: null
};

function applyHybrid(rows) {
  const out = rows.map(r => ({ ...r }));
  // Rules first where category empty
  for (const r of out) {
    if (!r.category) {
      const cat = rulesCategorize(r.description, state.rules);
      if (cat) r.category = cat;
    }
  }
  // Collect labeled data
  const labeled = out.filter(r => r.category && r.description);
  const cats = new Set(labeled.map(r => r.category));
  if (cats.size >= 2) {
    const nb = new NaiveBayes();
    nb.fit(labeled.map(r => r.description), labeled.map(r => r.category));
    state.model = nb;
    // Predict for uncategorized
    for (const r of out) {
      if (!r.category) r.category = nb.predictOne(r.description) || r.category;
    }
  }
  return out;
}

function renderKpis(rows) {
  const { expenses, income, net } = computeKpis(rows);
  document.getElementById('kpiExpenses').textContent = fmt(-expenses);
  document.getElementById('kpiIncome').textContent = fmt(income);
  document.getElementById('kpiNet').textContent = fmt(net);
}

let categoryChart, monthlyChart;
function renderCharts(rows) {
  const cat = groupByCategory(rows);
  const catCtx = document.getElementById('categoryChart');
  if (categoryChart) categoryChart.destroy();
  if (cat.length) {
    categoryChart = new Chart(catCtx, {
      type: 'pie',
      data: {
        labels: cat.map(x => x.Category),
        datasets: [{ data: cat.map(x => x.Spend), backgroundColor: cat.map((_,i)=>`hsl(${(i*47)%360} 70% 50%)`) }]
      },
      options: { plugins: { legend: { labels: { color: '#e2e8f0' } } } }
    });
  }

  const mon = groupByMonth(rows);
  const monCtx = document.getElementById('monthlyChart');
  if (monthlyChart) monthlyChart.destroy();
  if (mon.length) {
    monthlyChart = new Chart(monCtx, {
      type: 'bar',
      data: {
        labels: mon.map(x => x.Month),
        datasets: [
          { label: 'Spend', data: mon.map(x => x.Spend), backgroundColor: 'hsl(0 70% 55%)' },
          { label: 'Income', data: mon.map(x => x.Income), backgroundColor: 'hsl(140 70% 45%)' }
        ]
      },
      options: {
        responsive: true,
        plugins: { legend: { labels: { color: '#e2e8f0' } } },
        scales: { x: { ticks: { color: '#94a3b8' } }, y: { ticks: { color: '#94a3b8' } } }
      }
    });
  }
}

function renderTable(rows) {
  const tbody = document.querySelector('#txnTable tbody');
  tbody.innerHTML = '';
  for (let i = 0; i < rows.length; i++) {
    const r = rows[i];
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${r.date ? new Date(r.date).toISOString().slice(0,10) : ''}</td>
      <td>${r.description || ''}</td>
      <td>${r.merchant || ''}</td>
      <td class="${r.amount<0?'amount-neg':'amount-pos'}">${fmt(r.amount)}</td>
      <td><input class="category-input" data-idx="${i}" value="${r.category || ''}" /></td>
      <td>${r.type || ''}</td>
      <td>${r.account || ''}</td>
    `;
    tbody.appendChild(tr);
  }
}

function applyFilters() {
  const s = document.getElementById('startDate').value;
  const e = document.getElementById('endDate').value;
  let rows = state.rows.slice();
  if (s) rows = rows.filter(r => r.date && new Date(r.date) >= new Date(s));
  if (e) rows = rows.filter(r => r.date && new Date(r.date) <= new Date(e));
  state.filtered = rows;
  renderKpis(rows);
  renderCharts(rows);
  renderTable(rows);
  document.getElementById('kpis').classList.toggle('hidden', rows.length === 0);
  document.getElementById('charts').classList.toggle('hidden', rows.length === 0);
  document.getElementById('tablePanel').classList.toggle('hidden', rows.length === 0);
}

function asCSV(rows) {
  const header = ['date','description','merchant','amount','category','type','account'];
  const lines = [header.join(',')];
  for (const r of rows) {
    const row = header.map(k => {
      const v = r[k] == null ? '' : String(r[k]);
      if (/[",\n]/.test(v)) return '"' + v.replace(/"/g,'""') + '"';
      return v;
    });
    lines.push(row.join(','));
  }
  return lines.join('\n');
}

function initTemplateButton() {
  document.getElementById('downloadTemplate').addEventListener('click', () => {
    const data = [
      'date,description,amount,category',
      '2024-05-01,TRADER JOES #123,-45.67,Groceries',
      '2024-05-02,UBER TRIP 9Q8W2,-12.34,Transport',
      '2024-05-03,ACME PAYROLL,2500.00,Income'
    ].join('\n');
    const blob = new Blob([data], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'transactions_template.csv'; a.click();
    URL.revokeObjectURL(url);
  });
}

function initRuleForm() {
  document.getElementById('addRule').addEventListener('click', () => {
    const cat = document.getElementById('ruleCategory').value.trim();
    const pat = document.getElementById('rulePattern').value.trim();
    const status = document.getElementById('ruleStatus');
    if (!cat || !pat) { status.textContent = 'Please provide both category and pattern.'; return; }
    if (!state.rules[cat]) state.rules[cat] = [];
    try {
      const rx = pat.startsWith('/') ? new RegExp(pat.slice(1, pat.lastIndexOf('/')), pat.slice(pat.lastIndexOf('/')+1)) : new RegExp(pat, 'i');
      state.rules[cat].push(rx);
      saveRules(state.rules);
      status.textContent = `Rule added: ${cat} ← ${rx}`;
    } catch (e) {
      status.textContent = 'Invalid regex';
    }
  });
}

function initFileUpload() {
  document.getElementById('fileInput').addEventListener('change', async (ev) => {
    const file = ev.target.files[0];
    if (!file) return;
    const rows = await parseCSV(file);
    let normalized = canonicalize(rows);
    normalized = applyHybrid(normalized);
    state.rows = normalized;
    // initialize date filters
    const dates = normalized.map(r => r.date).filter(Boolean).map(d => new Date(d));
    if (dates.length) {
      const min = new Date(Math.min.apply(null, dates));
      const max = new Date(Math.max.apply(null, dates));
      const toStr = (d) => new Date(d.getTime() - d.getTimezoneOffset()*60000).toISOString().slice(0,10);
      document.getElementById('startDate').value = toStr(min);
      document.getElementById('endDate').value = toStr(max);
    }
    applyFilters();
  });
}

function initEdits() {
  document.getElementById('applyEdits').addEventListener('click', () => {
    const inputs = document.querySelectorAll('.category-input');
    inputs.forEach(inp => {
      const idx = parseInt(inp.dataset.idx, 10);
      state.rows[idx].category = inp.value.trim() || null;
    });
    // re-train
    state.rows = applyHybrid(state.rows);
    applyFilters();
  });
}

function initDownload() {
  document.getElementById('downloadCsv').addEventListener('click', () => {
    const csv = asCSV(state.filtered.length ? state.filtered : state.rows);
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'categorized_transactions.csv'; a.click();
    URL.revokeObjectURL(url);
  });
}

function main() {
  initTemplateButton();
  initRuleForm();
  initFileUpload();
  initEdits();
  initDownload();
}

document.addEventListener('DOMContentLoaded', main);