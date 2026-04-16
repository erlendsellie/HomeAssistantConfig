(function () {
  'use strict';

  const DATA_URL = '/local/inatur/data.json';
  const INATUR_BASE = 'https://www.inatur.no';

  let allOffers = [];
  let currentUser = null;
  let userSettings = {};
  let saveTimeout = null;

  // ============================
  // HA Authentication
  // ============================

  function findHATokens() {
    // HA stores tokens as 'hassTokens' - scan all keys just in case
    const candidates = ['hassTokens'];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.includes('Token') && !candidates.includes(key)) {
        candidates.push(key);
      }
    }

    for (const key of candidates) {
      try {
        const raw = localStorage.getItem(key);
        if (!raw) continue;
        const parsed = JSON.parse(raw);
        if (parsed && (parsed.access_token || parsed.refresh_token)) {
          console.log('[Inatur] Found tokens under key:', key);
          return parsed;
        }
      } catch {}
    }
    console.log('[Inatur] No tokens found in localStorage. Keys:', Object.keys(localStorage).join(', '));
    return null;
  }

  async function refreshToken(tokens) {
    const clientId = tokens.clientId || (location.origin + '/');
    try {
      const resp = await fetch('/auth/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          grant_type: 'refresh_token',
          client_id: clientId,
          refresh_token: tokens.refresh_token
        })
      });
      if (resp.ok) {
        const data = await resp.json();
        console.log('[Inatur] Token refreshed successfully');
        return data.access_token;
      } else {
        console.warn('[Inatur] Token refresh failed, status:', resp.status);
      }
    } catch (e) {
      console.warn('[Inatur] Token refresh error:', e);
    }
    return null;
  }

  async function getValidToken() {
    const tokens = findHATokens();
    if (!tokens) return null;

    // If access_token exists and not obviously expired, try it first
    if (tokens.access_token) {
      // Check expiry if available
      const expired = tokens.expires && (Date.now() / 1000 >= tokens.expires - 60);
      if (!expired) return tokens.access_token;
      console.log('[Inatur] Access token expired, refreshing...');
    }

    // Try refreshing
    if (tokens.refresh_token) {
      return await refreshToken(tokens);
    }

    return tokens.access_token || null;
  }

  async function getCurrentHAUser() {
    const token = await getValidToken();
    if (!token) return null;

    // Use REST API directly - faster and simpler than WebSocket
    try {
      const resp = await fetch('/api/', {
        headers: { 'Authorization': 'Bearer ' + token }
      });
      if (!resp.ok) {
        console.warn('[Inatur] /api/ returned', resp.status, '- token may be invalid');
        // Try refreshing once more if we get 401
        if (resp.status === 401) {
          const tokens = findHATokens();
          if (tokens && tokens.refresh_token) {
            const newToken = await refreshToken(tokens);
            if (newToken) return await getUserFromToken(newToken);
          }
        }
        return null;
      }
      return await getUserFromToken(token);
    } catch (e) {
      console.warn('[Inatur] REST API error:', e);
      return null;
    }
  }

  async function getUserFromToken(token) {
    // Use WebSocket to get actual user name (REST API doesn't expose current user directly)
    return new Promise((resolve) => {
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(proto + '//' + location.host + '/api/websocket');
      const timeout = setTimeout(() => {
        console.warn('[Inatur] WebSocket timeout');
        try { ws.close(); } catch {}
        // Return a partial user with token even if WS times out
        resolve({ name: 'Bruker', id: null, token });
      }, 4000);

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'auth_required') {
            ws.send(JSON.stringify({ type: 'auth', access_token: token }));
          } else if (msg.type === 'auth_ok') {
            ws.send(JSON.stringify({ id: 1, type: 'auth/current_user' }));
          } else if (msg.type === 'result' && msg.id === 1) {
            clearTimeout(timeout);
            ws.close();
            console.log('[Inatur] User:', msg.result.name);
            resolve({ name: msg.result.name, id: msg.result.id, token });
          } else if (msg.type === 'auth_invalid') {
            clearTimeout(timeout);
            ws.close();
            resolve(null);
          }
        } catch (e) {
          clearTimeout(timeout);
          ws.close();
          resolve(null);
        }
      };
      ws.onerror = () => { clearTimeout(timeout); resolve({ name: 'Bruker', id: null, token }); };
    });
  }

  // ============================
  // Per-user Settings via HA API
  // ============================

  function sanitizeUsername(name) {
    return name.toLowerCase().replace(/[^a-z0-9]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '');
  }

  async function loadSettings() {
    if (!currentUser) return {};

    // HA API path
    if (currentUser.token) {
      const entityId = 'sensor.inatur_user_' + sanitizeUsername(currentUser.name);
      try {
        const resp = await fetch('/api/states/' + entityId, {
          headers: { 'Authorization': 'Bearer ' + currentUser.token }
        });
        if (resp.ok) {
          const data = await resp.json();
          return (data.attributes && data.attributes.settings) || {};
        }
      } catch (e) {
        console.warn('[Inatur] Failed to load HA settings:', e);
      }
    }

    // localStorage fallback
    try {
      const key = 'inatur_settings_' + sanitizeUsername(currentUser.name);
      const stored = localStorage.getItem(key);
      if (stored) return JSON.parse(stored);
    } catch {}

    return {};
  }

  async function saveSettings() {
    if (!currentUser) return;

    if (currentUser.token) {
      const entityId = 'sensor.inatur_user_' + sanitizeUsername(currentUser.name);
      try {
        await fetch('/api/states/' + entityId, {
          method: 'POST',
          headers: {
            'Authorization': 'Bearer ' + currentUser.token,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            state: new Date().toISOString(),
            attributes: {
              friendly_name: 'Inatur Settings - ' + currentUser.name,
              settings: userSettings,
              last_updated: new Date().toISOString()
            }
          })
        });
        return;
      } catch (err) {
        console.warn('[Inatur] HA save failed, falling back to localStorage:', err);
      }
    }

    // localStorage fallback
    try {
      const key = 'inatur_settings_' + sanitizeUsername(currentUser.name);
      localStorage.setItem(key, JSON.stringify(userSettings));
    } catch {}
  }

  function debouncedSave() {
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(saveSettings, 800);
  }

  function getOfferSetting(offerId) {
    if (!userSettings.offerSettings) userSettings.offerSettings = {};
    if (!userSettings.offerSettings[offerId]) userSettings.offerSettings[offerId] = {};
    return userSettings.offerSettings[offerId];
  }

  function setOfferSetting(offerId, key, value) {
    const s = getOfferSetting(offerId);
    s[key] = value;
    debouncedSave();
  }

  // ============================
  // Data Loading
  // ============================

  async function fetchData() {
    const grid = document.getElementById('offersGrid');
    try {
      grid.innerHTML = '<div class="loading">Laster tilbud…</div>';
      const resp = await fetch(DATA_URL + '?t=' + Date.now());
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const data = await resp.json();

      allOffers = Object.entries(data).map(([id, offer]) => ({ id, ...offer }));

      const now = new Date();
      allOffers.forEach(o => {
        if (o.soknadsfrist_iso) {
          o.days_until_expiry = Math.ceil((new Date(o.soknadsfrist_iso) - now) / (1000 * 60 * 60 * 24));
        }
      });

      updateLastUpdated();
      populateFilters();
      renderOffers();
    } catch (err) {
      console.error('[Inatur] Fetch error:', err);
      grid.innerHTML =
        '<div class="loading">Kunne ikke laste data.<br><small style="opacity:0.6">' +
        err.message + '</small></div>';
    }
  }

  function updateLastUpdated() {
    document.getElementById('lastUpdated').textContent = 'Oppdatert: ' +
      new Date().toLocaleString('no-NO', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  // ============================
  // Filters
  // ============================

  function populateFilters() {
    const kommuner = [...new Set(allOffers.map(o => o.kommuner).filter(Boolean))].sort();
    const tilbydere = [...new Set(allOffers.map(o => o.tilbydernavn).filter(Boolean))].sort();
    const kSelect = document.getElementById('filterKommune');
    const tSelect = document.getElementById('filterTilbyder');
    const filters = userSettings.filters || {};

    kSelect.innerHTML = '<option value="">Alle kommuner</option>';
    kommuner.forEach(k => {
      const opt = document.createElement('option');
      opt.value = k; opt.textContent = k;
      if (filters.kommune === k) opt.selected = true;
      kSelect.appendChild(opt);
    });

    tSelect.innerHTML = '<option value="">Alle tilbydere</option>';
    tilbydere.forEach(t => {
      const opt = document.createElement('option');
      opt.value = t; opt.textContent = t;
      if (filters.tilbyder === t) opt.selected = true;
      tSelect.appendChild(opt);
    });

    if (filters.sort) document.getElementById('sortBy').value = filters.sort;
    if (filters.trekning) document.getElementById('filterTrekning').checked = true;
    if (filters.soktFilter) document.getElementById('filterSokt').checked = true;
    if (filters.expired) document.getElementById('filterExpired').checked = true;
    if (filters.search) document.getElementById('searchInput').value = filters.search;
  }

  function getFilteredOffers() {
    const kommune = document.getElementById('filterKommune').value;
    const tilbyder = document.getElementById('filterTilbyder').value;
    const trekning = document.getElementById('filterTrekning').checked;
    const soktFilter = document.getElementById('filterSokt').checked;
    const expiredFilter = document.getElementById('filterExpired').checked;
    const search = document.getElementById('searchInput').value.toLowerCase().trim();
    const sortBy = document.getElementById('sortBy').value;

    userSettings.filters = { kommune, tilbyder, trekning, soktFilter, expired: expiredFilter, search, sort: sortBy };
    debouncedSave();

    let filtered = allOffers.filter(o => {
      if (o.days_until_expiry < 0 && !expiredFilter) return false;
      if (kommune && o.kommuner !== kommune) return false;
      if (tilbyder && o.tilbydernavn !== tilbyder) return false;
      if (trekning && !o.harTrekning) return false;
      if (soktFilter) {
        const s = getOfferSetting(o.id);
        if (s.sokt) return false;
      }
      if (search) {
        const haystack = [o.tittel, o.kommuner, o.tilbydernavn, o.kortBeskrivelse, o.ai_summary || ''].join(' ').toLowerCase();
        if (!haystack.includes(search)) return false;
      }
      return true;
    });

    filtered.sort((a, b) => {
      switch (sortBy) {
        case 'deadline': return (a.days_until_expiry ?? 9999) - (b.days_until_expiry ?? 9999);
        case 'kommune': return (a.kommuner || '').localeCompare(b.kommuner || '', 'no');
        case 'tilbyder': return (a.tilbydernavn || '').localeCompare(b.tilbydernavn || '', 'no');
        case 'updated': return (b.sistOppdatertFormatert || '').localeCompare(a.sistOppdatertFormatert || '');
        default: return 0;
      }
    });

    return filtered;
  }

  // ============================
  // Rendering
  // ============================

  function getUrgencyClass(days) {
    if (days == null) return 'urgency-none';
    if (days < 0) return 'urgency-expired';
    if (days <= 7) return 'urgency-high';
    if (days <= 14) return 'urgency-medium';
    return 'urgency-low';
  }

  function getFristBadge(days) {
    if (days == null) return '';
    if (days < 0) return '<span class="badge badge-expired">Utløpt</span>';
    let cls = 'badge-frist-low';
    if (days <= 7) cls = 'badge-frist-high';
    else if (days <= 14) cls = 'badge-frist-medium';
    return `<span class="badge ${cls}">${days}d</span>`;
  }

  function esc(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
  }

  function renderOffers() {
    const grid = document.getElementById('offersGrid');
    const filtered = getFilteredOffers();

    // Stats
    const withDeadline = allOffers.filter(o => o.days_until_expiry != null);
    const urgent = allOffers.filter(o => o.days_until_expiry != null && o.days_until_expiry <= 7);
    const lottery = allOffers.filter(o => o.harTrekning);
    const soktCount = allOffers.filter(o => getOfferSetting(o.id).sokt).length;

    document.getElementById('statTotal').textContent = allOffers.length;
    document.getElementById('statDeadline').textContent = withDeadline.length;
    document.getElementById('statUrgent').textContent = urgent.length;
    document.getElementById('statLottery').textContent = lottery.length;
    document.getElementById('statSokt').textContent = soktCount;

    if (filtered.length === 0) {
      grid.innerHTML = '<div class="no-results">Ingen tilbud matcher filtrene.</div>';
      return;
    }

    grid.innerHTML = filtered.map((o, i) => {
      const urgency = getUrgencyClass(o.days_until_expiry);
      const fristBadge = getFristBadge(o.days_until_expiry);
      const trekningBadge = o.harTrekning ? '<span class="badge badge-trekning">🎲 Trekning</span>' : '';
      const setting = getOfferSetting(o.id);
      const soktBadge = setting.sokt ? '<span class="badge badge-sokt">✓ Søkt</span>' : '';
      const soktClass = setting.sokt ? ' is-sokt' : '';
      const soktActive = setting.sokt ? ' active' : '';
      const fristText = o.soknadsfrist_iso
        ? new Date(o.soknadsfrist_iso).toLocaleDateString('no-NO', { day: '2-digit', month: 'short', year: 'numeric' })
        : 'Ingen frist';
      const aiHtml = o.ai_summary ? `<div class="card-ai-summary">${esc(o.ai_summary)}</div>` : '';
      const notesHtml = setting.notes ? `<div class="card-notes-preview">${esc(setting.notes)}</div>` : '';
      const inaturUrl = INATUR_BASE + (o.url || '');

      return `
        <div class="offer-card ${urgency}${soktClass}" data-id="${o.id}" style="animation-delay:${Math.min(i * 0.03, 0.4)}s">
          <div class="card-header" data-action="modal" data-id="${o.id}">
            <div class="card-badges">${soktBadge}${fristBadge}${trekningBadge}</div>
            <div class="card-title">${esc(o.tittel)}</div>
          </div>
          <div class="card-meta">
            <span>📍 ${esc(o.kommuner || '—')}</span><span class="meta-sep">•</span>
            <span>${esc(o.tilbydernavn || '—')}</span><span class="meta-sep">•</span>
            <span>📅 ${fristText}</span>
          </div>
          ${o.kortBeskrivelse ? `<div class="card-desc">${esc(o.kortBeskrivelse)}</div>` : ''}
          ${notesHtml}
          <div class="card-actions">
            <a href="${esc(inaturUrl)}" target="_blank" rel="noopener" class="btn-card" onclick="event.stopPropagation()">Inatur</a>
            <a href="${esc(inaturUrl)}?v=2" target="_blank" rel="noopener" class="btn-card btn-auto" onclick="event.stopPropagation()" title="Autosøk alle kort">⚡ Auto</a>
            <button class="btn-card" data-action="modal" data-id="${o.id}">Detaljer</button>
            <label class="sokt-toggle${soktActive}" data-action="sokt" data-id="${o.id}">
              <input type="checkbox" ${setting.sokt ? 'checked' : ''}>
              ${setting.sokt ? 'Søkt' : 'Søkt?'}
            </label>
          </div>
        </div>`;
    }).join('');

    // Event delegation
    grid.querySelectorAll('[data-action="modal"]').forEach(el => {
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = el.dataset.id;
        const offer = allOffers.find(o => o.id === id);
        if (offer) showModal(offer);
      });
    });

    grid.querySelectorAll('[data-action="sokt"]').forEach(el => {
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        const id = el.dataset.id;
        const cb = el.querySelector('input');
        const newVal = !cb.checked;
        cb.checked = newVal;
        setOfferSetting(id, 'sokt', newVal);
        renderOffers();
      });
    });
  }

  // ============================
  // Modal
  // ============================

  function showModal(offer) {
    const modal = document.getElementById('modal');
    const body = document.getElementById('modalBody');
    const setting = getOfferSetting(offer.id);
    const fristText = offer.soknadsfrist_iso
      ? new Date(offer.soknadsfrist_iso).toLocaleDateString('no-NO', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
      : 'Ingen frist satt';
    const daysText = offer.days_until_expiry != null ? ` (${offer.days_until_expiry} dager igjen)` : '';
    const aiHtml = offer.ai_summary
      ? `<div class="modal-section"><div class="modal-section-label">🤖 AI Oppsummering</div><div class="modal-ai-summary">${esc(offer.ai_summary)}</div></div>` : '';
    const inaturUrl = INATUR_BASE + (offer.url || '');

    body.innerHTML = `
      <h2 class="modal-title">${esc(offer.tittel)}</h2>
      
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 32px; margin-bottom: 48px;">
        <div class="modal-section" style="margin-bottom:0">
          <div class="modal-section-label">📍 Kommune</div>
          <div class="modal-section-value" style="font-size: 1.2rem; color: #fff;">${esc(offer.kommuner || '—')}</div>
        </div>
        <div class="modal-section" style="margin-bottom:0">
          <div class="modal-section-label">🏢 Tilbyder</div>
          <div class="modal-section-value" style="font-size: 1.2rem; color: #fff;">${esc(offer.tilbydernavn || '—')}</div>
        </div>
        <div class="modal-section" style="margin-bottom:0">
          <div class="modal-section-label">📅 Frist</div>
          <div class="modal-section-value" style="font-size: 1.2rem; color: #fff;">${fristText}${daysText}</div>
        </div>
        <div class="modal-section" style="margin-bottom:0">
          <div class="modal-section-label">🎲 Type</div>
          <div class="modal-section-value" style="font-size: 1.2rem; color: #fff;">${offer.harTrekning ? 'Trekning' : 'Fastpris'}</div>
        </div>
      </div>

      <div class="modal-section">
        <div class="modal-section-label">◈ Beskrivelse</div>
        <div class="modal-section-value" style="font-size: 1.1rem;">${esc(offer.kortBeskrivelse || 'Ingen beskrivelse tilgjengelig.')}</div>
      </div>

      ${aiHtml}

      <div class="modal-section">
        <div class="modal-section-label">✎ Dine Feltnotater</div>
        <textarea class="modal-notes-area" id="modalNotes" placeholder="Skriv dine observasjoner fra fjellet her…">${esc(setting.notes || '')}</textarea>
      </div>

      <div class="modal-section">
        <div class="modal-section-label">Aksjoner</div>
        <div style="display: flex; gap: 16px; align-items: center;">
          <label class="modal-sokt-toggle${setting.sokt ? ' active' : ''}" id="modalSoktToggle">
            <input type="checkbox" ${setting.sokt ? 'checked' : ''}>
            ${setting.sokt ? '✓ Søknad er sendt' : '○ Ikke søkt ennå'}
          </label>
        </div>
      </div>

      <div class="modal-actions">
        <a href="${esc(inaturUrl)}" target="_blank" rel="noopener" class="btn-primary" style="padding: 16px 32px; font-size: 1.1rem;">↗ Se på Inatur.no</a>
        <a href="${esc(inaturUrl)}?v=2" target="_blank" rel="noopener" class="btn-primary" style="padding: 16px 32px; font-size: 1.1rem; background-color: #ff9800; border: none; color: #fff;">⚡ Auto-Søk på alt!</a>
      </div>
    `;

    // Notes handler
    const notesEl = document.getElementById('modalNotes');
    let notesTimer;
    notesEl.addEventListener('input', () => {
      clearTimeout(notesTimer);
      notesTimer = setTimeout(() => {
        setOfferSetting(offer.id, 'notes', notesEl.value);
      }, 500);
    });

    // Søkt toggle
    const soktToggle = document.getElementById('modalSoktToggle');
    soktToggle.addEventListener('click', () => {
      const cb = soktToggle.querySelector('input');
      const newVal = !cb.checked;
      cb.checked = newVal;
      soktToggle.classList.toggle('active', newVal);
      soktToggle.innerHTML = `<input type="checkbox" ${newVal ? 'checked' : ''}> ${newVal ? '✓ Har søkt' : '☐ Har ikke søkt'}`;
      setOfferSetting(offer.id, 'sokt', newVal);
      renderOffers();
    });

    modal.classList.remove('hidden');
  }

  function closeModal() {
    document.getElementById('modal').classList.add('hidden');
  }

  // ============================
  // Init
  // ============================

  async function init() {
    // Set up event listeners
    document.getElementById('filterKommune').addEventListener('change', renderOffers);
    document.getElementById('filterTilbyder').addEventListener('change', renderOffers);
    document.getElementById('filterTrekning').addEventListener('change', renderOffers);
    document.getElementById('filterSokt').addEventListener('change', renderOffers);
    document.getElementById('filterExpired').addEventListener('change', renderOffers);
    document.getElementById('sortBy').addEventListener('change', renderOffers);

    let debounce;
    document.getElementById('searchInput').addEventListener('input', () => {
      clearTimeout(debounce);
      debounce = setTimeout(renderOffers, 200);
    });

    document.getElementById('btnRefresh').addEventListener('click', fetchData);
    const bookmarkletSource = `javascript:(function(){const sleep=ms=>new Promise(r=>setTimeout(r,ms));async function start(){console.log("⚡ Starter...");const cards=document.querySelectorAll('.kortliste .kort, #kortliste .kort, article.kort');if(cards.length===0){alert("Fant ingen tilbudskort på denne siden.");return;}for(let c of cards){const ps=Array.from(c.querySelectorAll('p'));if(ps.find(p=>p.textContent.trim().toLowerCase()==='søknad')||c.innerText.includes("Søknad")){c.scrollIntoView({behavior:'auto',block:'center'});await sleep(500);if(!c.classList.contains('valgt')){c.click();await sleep(1000);}const u=document.querySelector('label[for^="prioritet-UTENBYGDS"], #prioritet-UTENBYGDS');if(u){u.click();await sleep(400);}const s=document.querySelector('button#sokPaKort, .sokPaKort button');if(s&&!s.disabled){s.click();await sleep(1200);}}}alert("Ferdig på denne siden!");}start();})();`;
    document.getElementById('bookmarkletCode').textContent = bookmarkletSource;
    document.getElementById('btnCopyBookmarklet').addEventListener('click', () => {
      navigator.clipboard.writeText(bookmarkletSource).then(() => {
        const btn = document.getElementById('btnCopyBookmarklet');
        const oldText = btn.textContent;
        btn.textContent = '✓ Kopiert!';
        btn.style.background = 'var(--emerald)';
        setTimeout(() => { btn.textContent = oldText; btn.style.background = ''; }, 2000);
      });
    });

    document.getElementById('btnHelp').addEventListener('click', () => {
      document.getElementById('helpModal').classList.remove('hidden');
    });
    document.getElementById('helpModalClose').addEventListener('click', () => {
      document.getElementById('helpModal').classList.add('hidden');
    });

    document.getElementById('btnBulk').addEventListener('click', () => {
      const filtered = getFilteredOffers();
      if (filtered.length === 0) {
        alert('Ingen tilbud å søke på med nåværende filter.');
        return;
      }
      document.getElementById('bulkModalDesc').textContent = `Du har valgt ${filtered.length} tilbud. Velg hvordan du vil utføre søknadene.`;
      document.getElementById('bulkModal').classList.remove('hidden');
    });

    document.getElementById('bulkModalClose').addEventListener('click', () => {
      document.getElementById('bulkModal').classList.add('hidden');
    });

    document.getElementById('btnBulkSeq').addEventListener('click', () => {
      const filtered = getFilteredOffers();
      const fullUrls = filtered.map(o => INATUR_BASE + (o.url || ''));
      const shortenedUrls = filtered.map(o => {
          const parts = (o.url || '').split('/');
          return parts.length > 3 ? parts.slice(0, 3).join('/') : (o.url || '');
      });
      const payload = btoa(JSON.stringify(shortenedUrls));
      const firstUrl = new URL(fullUrls[0]);
      firstUrl.searchParams.set('v', '2');
      firstUrl.searchParams.set('v2', payload);
      window.open(firstUrl.toString(), '_blank');
      document.getElementById('bulkModal').classList.add('hidden');
    });

    document.getElementById('btnBulkPar').addEventListener('click', () => {
      const filtered = getFilteredOffers();
      const fullUrls = filtered.map(o => INATUR_BASE + (o.url || ''));

      alert('Viktig: Du må tillate "pop-ups" (sprettoppvinduer) i nettleseren din for at dette skal fungere. \n\nSe etter et ikon øverst i adressefeltet og velg "Tillat alltid".');

      fullUrls.forEach((url, i) => {
          setTimeout(() => {
              const target = new URL(url);
              target.searchParams.set('v', '2');
              target.searchParams.set('close', '1');
              window.open(target.toString(), '_blank');
          }, i * 400);
      });
      document.getElementById('bulkModal').classList.add('hidden');
    });
    document.getElementById('modalClose').addEventListener('click', closeModal);
    document.getElementById('modal').addEventListener('click', (e) => { if (e.target === e.currentTarget) closeModal(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });

    // Load data immediately — don't wait for auth
    await fetchData();

    // Auth in background — re-renders once settings are loaded
    resolveUser();
  }

  async function resolveUser() {
    const userBadge = document.getElementById('currentUser');
    console.log('[Inatur] Resolving user...');

    currentUser = await getCurrentHAUser();

    if (currentUser) {
      userBadge.textContent = '👤 ' + currentUser.name;
      userSettings = await loadSettings();
      renderOffers(); // re-render with user settings
      return;
    }

    // No HA auth — check localStorage for saved username
    const savedName = localStorage.getItem('inatur_username');
    if (savedName) {
      currentUser = { name: savedName, id: null, token: null };
      userBadge.textContent = '👤 ' + savedName + ' (lokal)';
    } else {
      const name = prompt('Skriv inn brukernavnet ditt for å lagre notater og innstillinger:');
      if (name && name.trim()) {
        currentUser = { name: name.trim(), id: null, token: null };
        localStorage.setItem('inatur_username', name.trim());
        userBadge.textContent = '👤 ' + name.trim() + ' (lokal)';
      } else {
        currentUser = { name: 'gjest', id: null, token: null };
        userBadge.textContent = '👤 Gjest';
      }
    }

    userSettings = await loadSettings();
    renderOffers(); // re-render with user settings
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
