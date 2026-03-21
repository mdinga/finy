/* Finy Workspace JS
   Kept in one file for now. Split later once stable.
*/

'use strict';

/* API endpoints */
const API = (window.FINY && window.FINY.api) ? window.FINY.api : {
  folders: '/api/folders/',
  spaces: '/api/spaces/',
  tasks: '/api/tasks/',
  priority: '/api/tasks/priority/',
  today: '/api/tasks/today/',
  upcoming: '/api/tasks/upcoming/',
  spaceCategories: '/api/space-categories/',
  plannedRange: '/api/tasks/planned-range/'
};

function csrftoken(){ return document.getElementById('csrf')?.value || ''; }
function esc(s){ return (s||'').replace(/[&<>"']/g,m=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])); }

const MONTHS_SHORT = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function fmtUIDate(d){
  if(!d) return '';
  const dd = String(d.getDate()).padStart(2,'0');
  const m = MONTHS_SHORT[d.getMonth()];
  const yy = String(d.getFullYear()).slice(-2);
  return `${dd} ${m} '${yy}`;
}
function fmtUIDateFromISO(iso){
  try{ if(!iso) return ''; return fmtUIDate(new Date(iso)); }catch(e){ return ''; }
}
function fmtUIDateTimeFromISO(iso){
  try{
    if(!iso) return '';
    const d = new Date(iso);
    const date = fmtUIDate(d);
    const hh = String(d.getHours()).padStart(2,'0');
    const mm = String(d.getMinutes()).padStart(2,'0');
    return `${date} ${hh}:${mm}`;
  }catch(e){ return ''; }
}

const WEEKDAYS_SHORT = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];

function toISODate(d){
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2,'0');
  const day = String(d.getDate()).padStart(2,'0');
  return `${y}-${m}-${day}`;
}

function startOfDay(d){
  const x = new Date(d);
  x.setHours(0,0,0,0);
  return x;
}

function addDays(d, n){
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

function fmtDayHeader(d){
  const wd = WEEKDAYS_SHORT[d.getDay()];
  return `${wd} ${fmtUIDate(d)}`;
}

function fmtMinutesHuman(mins){
  const m = Number(mins || 0);
  if(!m) return '0 min';
  const h = Math.floor(m / 60);
  const r = m % 60;
  if(h && r) return `${h} h ${r} min`;
  if(h) return `${h} h`;
  return `${r} min`;
}




async function apiGet(url){
  const r = await fetch(url, { credentials:'same-origin' });
  if(!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}
async function apiSend(url, method, data, isForm=false){
  const opts = { method, credentials:'same-origin', headers: { 'X-CSRFToken': csrftoken() } };
  if(!isForm){
    opts.headers['Content-Type'] = 'application/json';
    if(data) opts.body = JSON.stringify(data);
  } else {
    opts.body = data;
  }
  const r = await fetch(url, opts);
  if(!r.ok){
    const msg = await r.text().catch(()=> '');
    throw new Error(`${r.status} ${url} ${msg}`);
  }
  return r.json().catch(()=> ({}));
}

/* State */
let inboxId = null;
let foldersCache = null;
let spacesCache = null;
let categoriesCache = null;
let activeFilter = { type:'inbox', id:null, name:'Inbox' };

const els = {
  list: document.getElementById('task-list'),
  newTaskForm: document.getElementById('new-task-form'),
  newTaskTitle: document.getElementById('nt-title'),
  inboxBadge: document.getElementById('inbox-count-badge'),
  listTitle: document.getElementById('list-title')
};

/* Calendar state and elements */
let activeView = 'list';
let calDays =7;
let calStart = null;

const calEls = {
  listView: document.getElementById('list-view'),
  calView: document.getElementById('calendar-view'),
  calList: document.getElementById('calendar-list'),
  calTitle: document.getElementById('calendar-title'),
  calPrev: document.getElementById('calPrev'),
  calNext: document.getElementById('calNext'),
  calBack: document.getElementById('calBackToList')
};

window.addEventListener('DOMContentLoaded', init);

async function init(){
  wireButtons();
  await loadCategories();
  await resolveInbox();
  await renderSidebar();
  await showInbox();
}

function wireButtons(){
  document.getElementById('showAddFolder')?.addEventListener('click', () => {
    document.getElementById('addFolderRow')?.classList.remove('d-none');
    document.getElementById('newFolderName')?.focus();
  });

  document.getElementById('showAddSpace')?.addEventListener('click', () => {
    document.getElementById('addSpaceRow')?.classList.remove('d-none');
    document.getElementById('newSpaceName')?.focus();
  });

  document.getElementById('btnInbox')?.addEventListener('click', showInbox);
  document.getElementById('btnPriority')?.addEventListener('click', showPriority);
  document.getElementById('btnShowToday')?.addEventListener('click', showToday);
  document.getElementById('btnShowUpcoming')?.addEventListener('click', showUpcoming);
  document.getElementById('btnCompleted')?.addEventListener('click', showCompleted);

  document.getElementById('btnCalendar')?.addEventListener('click', showCalendar);
  calEls.calPrev?.addEventListener('click', () => shiftCalendar(-calDays));
  calEls.calNext?.addEventListener('click', () => shiftCalendar(calDays));
  calEls.calBack?.addEventListener('click', () => showListView());

  els.newTaskForm?.addEventListener('submit', onCreateSubmit);
}

async function showCalendar(){
  activeView = 'calendar';
  if(calEls.listView) calEls.listView.classList.add('d-none');
  if(calEls.calView) calEls.calView.classList.remove('d-none');

  calStart = startOfDay(new Date());
  await renderCalendarRange();
}

function showListView(){
  activeView = 'list';
  if(calEls.calView) calEls.calView.classList.add('d-none');
  if(calEls.listView) calEls.listView.classList.remove('d-none');
}

async function shiftCalendar(deltaDays){
  if(!calStart) calStart = startOfDay(new Date());
  calStart = startOfDay(addDays(calStart, deltaDays));
  await renderCalendarRange();
}

async function renderCalendarRange(){
  if(!calEls.calList) return;

  const center = calStart || startOfDay(new Date());
  const today = startOfDay(new Date());
  const start = startOfDay(addDays(center, -3));
  const end = startOfDay(addDays(center, 3));

  const startISO = toISODate(start);
  const endISO = toISODate(end);

  if(calEls.calTitle){
    calEls.calTitle.textContent = `Planned Tasks · ${fmtUIDate(start)} to ${fmtUIDate(end)}`;
  }

  let tasks = [];
  try{
    tasks = await apiGet(`${API.plannedRange}?start=${startISO}&end=${endISO}&include_completed=true`);
  }catch(e){
    tasks = [];
  }

  const byDay = {};
  for(let i = 0; i <= 6; i++){
    const d = startOfDay(addDays(start, i));
    byDay[toISODate(d)] = [];
  }

  (tasks || []).forEach(t => {
    if(!t || !t.planned_date) return;
    if(byDay[t.planned_date]){
      byDay[t.planned_date].push(t);
    }
  });

  Object.keys(byDay).forEach(k => {
    byDay[k].sort((a,b) => {
      const ac = a.completed ? 1 : 0;
      const bc = b.completed ? 1 : 0;
      if(ac !== bc) return ac - bc;

      const ad = a.due_date ? new Date(a.due_date).getTime() : Number.POSITIVE_INFINITY;
      const bd = b.due_date ? new Date(b.due_date).getTime() : Number.POSITIVE_INFINITY;
      return ad - bd;
    });
  });

  calEls.calList.innerHTML = '';

  for(let i = 0; i <= 6; i++){
    const d = startOfDay(addDays(start, i));
    const iso = toISODate(d);
    const dayTasks = byDay[iso] || [];

    calEls.calList.appendChild(buildCalendarSection(d, dayTasks, today));
  }
}

function buildCalendarSection(dateObj, tasks, today){
  const section = document.createElement('section');
  section.className = 'calendar-section';

  const heading = document.createElement('div');
  heading.className = 'calendar-section-header';

  let label = fmtDayHeader(dateObj);

  const dayTime = startOfDay(dateObj).getTime();
  const todayTime = startOfDay(today).getTime();

  if(dayTime < todayTime){
    label = `Past · ${fmtDayHeader(dateObj)}`;
  }else if(dayTime === todayTime){
    label = `Today · ${fmtDayHeader(dateObj)}`;
  }else if(dayTime === startOfDay(addDays(today, 1)).getTime()){
    label = `Tomorrow · ${fmtDayHeader(dateObj)}`;
  }

  const total = (tasks || []).reduce((sum, t) => sum + (t.estimated_minutes ? Number(t.estimated_minutes) : 0), 0);

  heading.innerHTML = `
    <div>
      <h3 class="calendar-section-title">${esc(label)}</h3>
      <div class="calendar-section-sub">${tasks.length} tasks · ${esc(fmtMinutesHuman(total))}</div>
    </div>
  `;

  section.appendChild(heading);

  const body = document.createElement('div');
  body.className = 'calendar-section-body';

  if(!tasks.length){
    body.innerHTML = `<div class="text-muted small">No planned tasks.</div>`;
  }else{
    tasks.forEach(t => body.appendChild(buildTaskCard(t)));
  }

  section.appendChild(body);
  return section;
}


async function openTaskModal(taskId){
  const body = document.getElementById('taskModalBody');
  const title = document.getElementById('taskModalTitle');
  if(!body || !title) return;

  const t = await apiGet(`${API.tasks}${taskId}/`);
  title.textContent = t && t.title ? t.title : 'Task';

  body.innerHTML = `
    <div id="details-${t.id}" class="mt-1">
      ${buildDetailsPanel(t)}
    </div>
  `;

  const modalEl = document.getElementById('taskModal');
  if(modalEl && window.bootstrap){
    const m = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    m.show();
  }
}
window.openTaskModal = openTaskModal;

function hideInline(id){ document.getElementById(id)?.classList.add('d-none'); }
window.hideInline = hideInline;

async function loadCategories(){
  try{
    const res = await apiGet(API.spaceCategories);
    const list = res.results || res || [];
    categoriesCache = list.map(c => ({ id:c.id, name:c.name }));
  } catch(e){
    categoriesCache = [];
  }
  fillSelect('qcSpaceCategory');
  fillSelect('newSpaceCategory');
}

function fillSelect(id){
  const el = document.getElementById(id);
  if(!el) return;
  el.innerHTML = categoriesCache.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join('');
}

async function resolveInbox(){
  const folders = await apiGet(API.folders);
  const list = folders.results || folders || [];
  const inbox = list.find(f => f.is_inbox);
  inboxId = inbox ? inbox.id : null;
}

async function renderSidebar(){
  const fRes = await apiGet(API.folders);
  foldersCache = fRes.results || fRes || [];

  const sRes = await apiGet(API.spaces);
  spacesCache = sRes.results || sRes || [];

  const folders = foldersCache.filter(f => !f.is_inbox).sort((a,b)=>a.name.localeCompare(b.name));
  const folderCounts = Object.fromEntries(await Promise.all(folders.map(async f => {
    const r = await apiGet(`${API.tasks}?folder=${f.id}&completed=false&page_size=1`);
    const c = typeof r.count === 'number' ? r.count : (r.results || r || []).length;
    return [f.id, c];
  })));

  const folderList = document.getElementById('folderList');
  if(folderList){
    folderList.innerHTML = folders.map(f => (
      `<li class="list-group-item d-flex align-items-center" data-id="${f.id}">
        <button class="btn btn-link btn-sm text-decoration-none text-reset list-title-btn" onclick="filterByFolder('${f.id}')">${esc(f.name)}</button>
        <span id="folder-count-${f.id}" class="badge rounded-pill count-badge me-2">${folderCounts[f.id] ?? 0}</span>
        <div class="dropdown kebab">
          <button class="btn btn-plain btn-sm btn-kebab" data-bs-toggle="dropdown" aria-expanded="false" aria-label="Folder actions">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/></svg>
          </button>
          <ul class="dropdown-menu dropdown-menu-end">
            <li><button class="dropdown-item" onclick="startEditFolder('${f.id}')">Edit</button></li>
            <li><button class="dropdown-item text-danger" onclick="deleteFolder('${f.id}')">Delete</button></li>
          </ul>
        </div>
      </li>`
    )).join('');
  }

  const spaces = (spacesCache || []).sort((a,b)=>a.name.localeCompare(b.name));
  const spaceCounts = Object.fromEntries(await Promise.all(spaces.map(async s => {
    const r = await apiGet(`${API.tasks}?spaces=${s.id}&completed=false&page_size=1`);
    const c = typeof r.count === 'number' ? r.count : (r.results || r || []).length;
    return [s.id, c];
  })));

  const spaceList = document.getElementById('spaceList');
  if(spaceList){
    spaceList.innerHTML = spaces.map(s => (
      `<li class="list-group-item d-flex align-items-center" data-id="${s.id}">
        <button class="btn btn-link btn-sm text-decoration-none text-reset list-title-btn" onclick="filterBySpace('${s.id}')">${esc(s.name)}</button>
        <span id="space-count-${s.id}" class="badge rounded-pill count-badge me-2">${spaceCounts[s.id] ?? 0}</span>
        <div class="dropdown kebab">
          <button class="btn btn-plain btn-sm btn-kebab" data-bs-toggle="dropdown" aria-expanded="false" aria-label="Space actions">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/></svg>
          </button>
          <ul class="dropdown-menu dropdown-menu-end">
            <li><button class="dropdown-item" onclick="startEditSpace('${s.id}')">Edit</button></li>
            <li><button class="dropdown-item text-danger" onclick="deleteSpace('${s.id}')">Delete</button></li>
          </ul>
        </div>
      </li>`
    )).join('');
  }

  if(inboxId && els.inboxBadge){
    const inboxRes = await apiGet(`${API.tasks}?folder=${inboxId}&completed=false&page_size=1`);
    const inboxCount = typeof inboxRes.count === 'number' ? inboxRes.count : (inboxRes.results || inboxRes || []).length;
    els.inboxBadge.textContent = String(inboxCount);
  }

  const completedBadge = document.getElementById('completed-count-badge');
    if(completedBadge){
      const r = await apiGet(`${API.tasks}?completed=true&page_size=1`);
      const c = typeof r.count === 'number' ? r.count : (r.results || r || []).length;
      completedBadge.textContent = String(c);
    }


}

/* Filters */
async function filterByFolder(folderId){
  showListView();
  const f = (foldersCache || []).find(x => String(x.id) === String(folderId));
  activeFilter = { type:'folder', id: parseInt(folderId,10), name: f ? f.name : 'Folder' };
  await renderListByFilter();
}
window.filterByFolder = filterByFolder;

async function filterBySpace(spaceId){
  showListView();
  const s = (spacesCache || []).find(x => String(x.id) === String(spaceId));
  activeFilter = { type:'space', id: parseInt(spaceId,10), name: s ? s.name : 'Space' };
  await renderListByFilter();
}
window.filterBySpace = filterBySpace;

async function showInbox(){
  showListView();
  activeFilter = { type:'inbox', id: inboxId, name:'Inbox' };
  await renderListByFilter();
}
async function showPriority(){
  showListView();
  activeFilter = { type:'priority', id:null, name:'Priority' };
  await renderListByFilter();
}
async function showToday(){
  showListView();
  activeFilter = { type:'today', id:null, name:'Today' };
  await renderListByFilter();
}
async function showUpcoming(){
  showListView();
  activeFilter = { type:'upcoming', id:null, name:'Upcoming' };
  await renderListByFilter();
}
async function showCompleted(){
  showListView();
  activeFilter = { type:'completed', id:null, name:'Completed Tasks' };
  await renderListByFilter();
}


/* New task */
async function onCreateSubmit(e){
  e.preventDefault();
  const title = (els.newTaskTitle.value || '').trim();
  if(!title) return;
  if(!inboxId){ alert('No Inbox found'); return; }
  await apiSend(API.tasks, 'POST', { title, folder: inboxId });
  els.newTaskTitle.value = '';
  await renderListByFilter();
  await renderSidebar();
}

/* Create folder or space */
async function createFolder(nameId, descId){
  const nameEl = document.getElementById(nameId);
  const descEl = descId ? document.getElementById(descId) : null;

  const name = (nameEl?.value || '').trim();
  const description = (descEl?.value || '').trim();
  if(!name) return;

  await apiSend(API.folders, 'POST', { name, description });
  if(nameEl) nameEl.value = '';
  if(descEl) descEl.value = '';
  document.getElementById('addFolderRow')?.classList.add('d-none');
  await renderSidebar();
}
window.createFolder = createFolder;

async function createSpace(nameId, catSelectId){
  const nameEl = document.getElementById(nameId);
  const catEl = document.getElementById(catSelectId);

  const name = (nameEl?.value || '').trim();
  const category = parseInt(catEl?.value || '0', 10);

  if(!name || !category){
    const msg = 'Please add a name and choose a category.';
    const q = document.getElementById('quickCreateError');
    const s = document.getElementById('spaceCreateError');
    if(q){ q.classList.remove('d-none'); q.textContent = msg; }
    if(s){ s.classList.remove('d-none'); s.textContent = msg; }
    return;
  }

  await apiSend(API.spaces, 'POST', { name, category });
  if(nameEl) nameEl.value = '';
  document.getElementById('addSpaceRow')?.classList.add('d-none');
  document.getElementById('quickCreateError')?.classList.add('d-none');
  document.getElementById('spaceCreateError')?.classList.add('d-none');
  await renderSidebar();
}
window.createSpace = createSpace;

/* List rendering */
async function renderListByFilter(){
  showListView();  

  if(els.listTitle){
    if(activeFilter?.type === 'today'){
      els.listTitle.textContent = `Today · ${fmtTodayLabel()}`;
    } else {
      els.listTitle.textContent = activeFilter?.name || 'Tasks';
    }
  }


  let res;
  if(activeFilter.type === 'inbox'){
    res = await apiGet(`${API.tasks}?folder=${inboxId}&ordering=due_date`);
  } else if(activeFilter.type === 'priority'){
    res = await apiGet(API.priority);
  } else if(activeFilter.type === 'today'){
    res = await apiGet(API.today);
  } else if(activeFilter.type === 'upcoming'){
    res = await apiGet(API.upcoming);
  } else if(activeFilter.type === 'folder'){
    res = await apiGet(`${API.tasks}?folder=${activeFilter.id}&ordering=due_date`);
  } else if(activeFilter.type === 'space'){
    res = await apiGet(`${API.tasks}?spaces=${activeFilter.id}&ordering=due_date`);
  } else if(activeFilter.type === 'completed'){
    res = await apiGet(`${API.tasks}?completed=true&ordering=-updated_at`);
  } else {
    res = await apiGet(`${API.tasks}?ordering=due_date`);
  }


  let tasks = res.results || res || [];
  if(activeFilter.type === 'completed') tasks = tasks.filter(t => t.completed);

  renderTasks(tasks);
  await renderSidebar();
}

/* Task rendering */
function renderTasks(tasks){
  if(!els.list) return;
  els.list.innerHTML = '';

  if(!tasks.length){
    els.list.innerHTML = `<div class="text-muted small p-3">No tasks here yet.</div>`;
    return;
  }

  const sorted = tasks.slice().sort((a,b) => {
    const ac = a.completed ? 1 : 0;
    const bc = b.completed ? 1 : 0;
    if(ac !== bc) return ac - bc; // incomplete first

    const ad = a.due_date ? new Date(a.due_date).getTime() : Number.POSITIVE_INFINITY;
    const bd = b.due_date ? new Date(b.due_date).getTime() : Number.POSITIVE_INFINITY;
    return ad - bd;
  });

  sorted.forEach(t => els.list.appendChild(buildTaskCard(t)));
}


function buildTaskCard(t){
  const wrap = document.createElement('div');
  wrap.className = 'card task-card mb-2' + (t.completed ? ' task-completed' : '');

  const due = t.due_date ? fmtUIDateFromISO(t.due_date) : '';
  const today = new Date();
  today.setHours(0,0,0,0);
  let overdue = false;
  if (t.due_date && !t.completed) {
    const dueDate = new Date(t.due_date);
    dueDate.setHours(0,0,0,0);
    overdue = dueDate < today;
  }
  const planned = t.planned_date ? fmtUIDateFromISO(t.planned_date) : '';
  const est = t.estimated_minutes ? `${t.estimated_minutes} min` : '';
  const completedAt = t.completed_at ? fmtUIDateTimeFromISO(t.completed_at) : '';

  const spaces = (t.spaces_display || '').trim();
  const folderName = (t.folder_name || '').trim();

  wrap.innerHTML = `
    <div class="card-body">
      <div class="d-flex justify-content-between align-items-start gap-2 task-toggle" data-task-id="${t.id}">
        <div class="flex-grow-1">
          <div class="d-flex align-items-center gap-2">
            <input type="checkbox" ${t.completed ? 'checked' : ''} onclick="event.stopPropagation()" onchange="toggleComplete(${t.id})">
            <h3 class="m-0 ${t.completed ? 'text-decoration-line-through text-muted' : ''}">
              ${esc(t.title)}
            </h3>

          </div>

          <div class="meta-icons mt-1">
            ${folderName ? `<span class="me-2">📁 ${esc(folderName)}</span>` : ''}
            ${spaces ? `<span class="me-2">🏷️ ${esc(spaces)}</span>` : ''}
            ${planned ? `<span class="me-2">🗓️ ${esc(planned)}</span>` : ''}
            ${!t.completed && due ? `<span class="me-2">⏰ ${esc(due)}</span>` : ''}
            ${est ? `<span class="me-2">⏳ ${esc(est)}</span>` : ''}
            ${t.is_priority ? `<span class="badge text-bg-warning">Priority</span>` : ''}
            ${overdue ? `<span class="badge text-bg-danger ms-2">Overdue</span>` : ''}
            ${t.completed && completedAt ? `<span class="me-2">✅ Completed ${esc(completedAt)}</span>` : ''}
          </div>
        </div>

        <button class="btn btn-plain btn-sm" onclick="event.stopPropagation(); openDetails(${t.id})">Open</button>
      </div>

      <div id="details-${t.id}" class="mt-3 d-none">
        ${buildDetailsPanel(t)}
      </div>
    </div>
  `;
  return wrap;
}

function buildDetailsPanel(t){
  const planned = t.planned_date || '';
  const due = t.due_date || '';
  const est = t.estimated_minutes || '';
  const repeat = t.repeat_rule || '';

  const folderId = t.folder ? String(t.folder) : '';
  const selectedSpaces = Array.isArray(t.spaces) ? t.spaces.map(x => String(x)) : [];

  return `
    <div class="border-top pt-3">
      <div class="d-flex gap-2 mb-3">
        <button class="btn btn-plain btn-sm tab-btn active" onclick="showTab(${t.id}, 'details')">Details</button>
        <button class="btn btn-plain btn-sm tab-btn" onclick="showTab(${t.id}, 'actions')">Next Actions</button>
        <button class="btn btn-plain btn-sm tab-btn" onclick="showTab(${t.id}, 'notes')">Notes</button>
        <button class="btn btn-plain btn-sm tab-btn" onclick="showTab(${t.id}, 'attachments')">Attachments</button>
      </div>

      <div id="tab-${t.id}-details" class="tab-panel show">
        <div class="row g-2">

        <div class="col-12 col-lg-4">
          <label class="form-label small">Folder</label>
          ${buildFolderSelectHtml(t.id, folderId)}
        </div>


        <div class="col-12 col-lg-8">
          <div class="d-flex align-items-center gap-2">
            <label class="form-label small mb-0">Spaces</label>
            <button type="button" class="btn btn-plain btn-xs space-toggle" onclick="toggleSpaces(${t.id}, this)">
              <span class="caret">▾</span>
            </button>
          </div>

          <div id="spaces-summary-${t.id}" class="small text-muted mt-1">
            ${buildSpacesSummaryHtml(selectedSpaces)}
          </div>

          <div id="spaces-panel-${t.id}" class="border rounded p-2 mt-2 d-none">
            ${buildSpacesChecklistHtml(t.id, selectedSpaces)}
          </div>
        </div>




          <div class="col-12 col-md-4">
            <label class="form-label small">Planned date</label>
            <input class="form-control form-control-sm" id="planned-${t.id}" type="date" value="${esc(planned)}">
          </div>
          <div class="col-12 col-md-4">
            <label class="form-label small">Due date</label>
            <input class="form-control form-control-sm" id="due-${t.id}" type="date" value="${esc(due)}">
          </div>
          <div class="col-12 col-md-4">
            <label class="form-label small">Estimated minutes</label>
            <input class="form-control form-control-sm" id="est-${t.id}" type="number" min="0" value="${esc(String(est))}">
          </div>

          <div class="col-12 col-md-6">
            <label class="form-label small">Repeat</label>
            <input class="form-control form-control-sm" id="repeat-${t.id}" placeholder="e.g. WEEKLY" value="${esc(repeat)}">
          </div>
        </div>

        <div class="d-flex justify-content-end gap-2 mt-3">
          <button class="btn btn-plain btn-sm" onclick="saveDetails(${t.id})">Save details</button>
          <button class="btn btn-plain btn-sm text-danger" onclick="deleteTask(${t.id})">Delete task</button>
        </div>


        <div id="save-msg-${t.id}" class="small text-success mt-2 d-none">Saved.</div>
        <div id="save-err-${t.id}" class="small text-danger mt-2 d-none"></div>
      </div>

      <div id="tab-${t.id}-actions" class="tab-panel">
        <div class="d-flex gap-2 mb-2">
          <input id="new-action-${t.id}" class="form-control form-control-sm" placeholder="Add a next action">
          <button class="btn btn-plain btn-sm" onclick="addAction(${t.id})">Add</button>
        </div>
        <ul id="actions-list-${t.id}" class="list-unstyled mb-0"></ul>
      </div>

      <div id="tab-${t.id}-notes" class="tab-panel">
        <div class="d-flex gap-2 mb-2">
          <textarea id="new-note-${t.id}" class="form-control form-control-sm" rows="2" placeholder="Add a note"></textarea>
          <button class="btn btn-plain btn-sm" onclick="addNote(${t.id})">Add</button>
        </div>
        <div id="notes-list-${t.id}"></div>
      </div>

      <div id="tab-${t.id}-attachments" class="tab-panel">
        <div class="text-muted small">Attachments coming soon.</div>
      </div>
    </div>
  `;
}

function buildFolderSelectHtml(taskId, folderId){
  const list = (foldersCache || []).slice().sort((a,b)=>a.name.localeCompare(b.name));
  const options = list.map(f => {
    const sel = String(f.id) === String(folderId) ? 'selected' : '';
    return `<option value="${f.id}" ${sel}>${esc(f.name)}</option>`;
  }).join('');

  return `<select class="form-select form-select-sm" id="folder-${taskId}">${options}</select>`;
}

function buildSpacesChecklistHtml(taskId, selectedSpaceIds){
  const spaces = (spacesCache || []).slice().sort((a,b)=>a.name.localeCompare(b.name));
  const cats = (categoriesCache || []).slice().sort((a,b)=>a.name.localeCompare(b.name));
  const catNameById = Object.fromEntries(cats.map(c => [String(c.id), c.name]));

  const byCat = {};
  spaces.forEach(s => {
    const cid = String(s.category || '');
    const cname = catNameById[cid] || 'Other';
    if(!byCat[cname]) byCat[cname] = [];
    byCat[cname].push(s);
  });

  const catNames = Object.keys(byCat).sort((a,b)=>a.localeCompare(b));

  const cols = catNames.map(cname => {
    const items = byCat[cname].map(s => {
      const checked = selectedSpaceIds.includes(String(s.id)) ? 'checked' : '';
      return `
        <label class="space-item">
          <input type="checkbox" class="space-check-${taskId}" value="${s.id}" ${checked}>
          <span>${esc(s.name)}</span>
        </label>
      `;
    }).join('');

    return `
      <div class="space-cat">
        <div class="space-cat-title">${esc(cname)}</div>
        <div class="space-cat-items">
          ${items}
        </div>
      </div>
    `;
  }).join('');

  return `<div class="space-cats">${cols}</div>`;
}

function buildSpacesSummaryHtml(selectedSpaceIds){
  const all = spacesCache || [];
  const selected = new Set((selectedSpaceIds || []).map(x => String(x)));

  const names = all
    .filter(s => selected.has(String(s.id)))
    .map(s => s.name);

  if(!names.length) return 'None selected';

  const first = names.slice(0, 3).join(', ');
  const extra = names.length > 3 ? ` +${names.length - 3} more` : '';
  return `${names.length} selected: ${esc(first)}${extra}`;
}

function toggleSpaces(taskId, btn){
  const panel = document.getElementById('spaces-panel-' + taskId);
  if(!panel) return;

  const isOpen = !panel.classList.contains('d-none');
  panel.classList.toggle('d-none');

  if(btn){
    btn.classList.toggle('open', !isOpen);
  }
}
window.toggleSpaces = toggleSpaces;



function showTab(taskId, tab){
  const root = document.getElementById('details-' + taskId);
  if(!root) return;

  root.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('show'));
  root.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));

  const panel = document.getElementById(`tab-${taskId}-${tab}`);
  if(panel) panel.classList.add('show');

  const buttons = root.querySelectorAll('.tab-btn');
  const tabMap = ['details','actions','notes','attachments'];
  const idx = tabMap.indexOf(tab);
  if(idx >= 0 && buttons[idx]) buttons[idx].classList.add('active');

  if(tab === 'notes') loadNotes(taskId);
  if(tab === 'actions') loadActions(taskId);
}
window.showTab = showTab;

async function openDetails(taskId){
  const el = document.getElementById('details-' + taskId);
  if(!el) return;
  el.classList.toggle('d-none');
  if(!el.classList.contains('d-none')){
    await loadNotes(taskId);
    await loadActions(taskId);
  }
}
window.openDetails = openDetails;

async function toggleComplete(taskId){
  await apiSend(`${API.tasks}${taskId}/complete/`, 'POST', {});
  await renderListByFilter();
}
window.toggleComplete = toggleComplete;

async function saveDetails(taskId){
  const planned = document.getElementById('planned-' + taskId)?.value || null;
  const due = document.getElementById('due-' + taskId)?.value || null;
  const est = document.getElementById('est-' + taskId)?.value || null;
  const repeat = document.getElementById('repeat-' + taskId)?.value || '';

  const folderVal = document.getElementById('folder-' + taskId)?.value || null;

  const spaceChecks = Array.from(document.querySelectorAll('.space-check-' + taskId));
  const spaces = spaceChecks
    .filter(ch => ch.checked)
    .map(ch => parseInt(ch.value, 10))
    .filter(n => Number.isFinite(n));

  const payload = {
    folder: folderVal ? parseInt(folderVal, 10) : null,
    spaces: spaces,
    planned_date: planned || null,
    due_date: due || null,
    estimated_minutes: est ? parseInt(est,10) : null,
    repeat_rule: repeat || ''
  };

  const msg = document.getElementById('save-msg-' + taskId);
  const err = document.getElementById('save-err-' + taskId);

  if(msg) msg.classList.add('d-none');
  if(err){
    err.classList.add('d-none');
    err.textContent = '';
  }

  try{
    await apiSend(`${API.tasks}${taskId}/`, 'PATCH', payload);

    const summary = document.getElementById('spaces-summary-' + taskId);
    if(summary){
      summary.innerHTML = buildSpacesSummaryHtml(spaces.map(String));
    }

    if(msg){
      msg.classList.remove('d-none');
      setTimeout(() => msg.classList.add('d-none'), 1200);
    }

    await renderListByFilter();
  }catch(e){
    if(err){
      err.textContent = 'Due date cannot be before planned date.';
      err.classList.remove('d-none');
    }else{
      alert('Due date cannot be before planned date.');
    }
  }
}
window.saveDetails = saveDetails;

async function deleteTask(taskId){
  const msg =
    'Delete this task permanently.\n\n' +
    'This is not the same as completing it.\n' +
    'Deleting will remove the task, its notes, next actions, and attachments.\n\n' +
    'Click OK to delete, or Cancel to keep it.';

  if(!confirm(msg)) return;

  await apiSend(`${API.tasks}${taskId}/`, 'DELETE', null);
  await renderListByFilter();
  await renderSidebar();
}
window.deleteTask = deleteTask;


/* Notes */
async function loadNotes(taskId){
  const listEl = document.getElementById('notes-list-' + taskId);
  if(!listEl) return;
  listEl.innerHTML = '';

  const res = await apiGet(`${API.tasks}${taskId}/notes/`);
  const notes = res.results || res || [];

  if(!notes.length){
    listEl.innerHTML = `<div class="text-muted small">No notes yet.</div>`;
    return;
  }

  notes.forEach(n => {
    const wrap = document.createElement('div');
    wrap.className = 'border rounded p-2 mb-2';
    wrap.id = 'note-' + n.id;

    const created = n.created_at_display ? n.created_at_display : fmtUIDateTimeFromISO(n.created_at);

    wrap.innerHTML = `
      <div class="d-flex justify-content-between align-items-start gap-2">
        <div class="flex-grow-1">
          <div id="note-text-display-${n.id}" class="small">${esc(n.text)}</div>
          <div class="text-muted small mt-1">${esc(created)}</div>
        </div>
        <div class="d-flex gap-2">
          <button class="btn btn-plain btn-sm" onclick="startEditNote('${taskId}', '${n.id}')">Edit</button>
          <button class="btn btn-plain btn-sm" onclick="deleteNote('${taskId}', '${n.id}')">Delete</button>
        </div>
      </div>
    `;
    listEl.appendChild(wrap);
  });
}

async function addNote(taskId){
  const input = document.getElementById('new-note-' + taskId);
  const text = (input?.value || '').trim();
  if(!text) return;

  await apiSend(`${API.tasks}${taskId}/notes/`, 'POST', { text });
  if(input) input.value = '';
  await loadNotes(taskId);
}
window.addNote = addNote;

function startEditNote(taskId, noteId){
  const wrapper = document.getElementById('note-' + noteId);
  if(!wrapper) return;

  const display = document.getElementById('note-text-display-' + noteId);
  const currentText = display ? display.textContent : '';

  wrapper.innerHTML =
    '<form onsubmit="event.preventDefault(); saveNote(\'' + taskId + '\', \'' + noteId + '\');">' +
      '<textarea id="note-edit-' + noteId + '" class="form-control mb-2" rows="2">' + esc(currentText) + '</textarea>' +
      '<div class="d-flex justify-content-end gap-2">' +
        '<button type="button" class="btn btn-plain btn-sm" onclick="cancelEditNote(\'' + taskId + '\')">Cancel</button>' +
        '<button type="submit" class="btn btn-plain btn-sm">Save</button>' +
      '</div>' +
    '</form>';
}
window.startEditNote = startEditNote;

function cancelEditNote(taskId){
  loadNotes(taskId);
}
window.cancelEditNote = cancelEditNote;

async function saveNote(taskId, noteId){
  const text = (document.getElementById('note-edit-' + noteId)?.value || '').trim();
  if(!text) return;

  await apiSend(`${API.tasks}${taskId}/notes/${noteId}/`, 'PATCH', { text });
  await loadNotes(taskId);
}
window.saveNote = saveNote;

async function deleteNote(taskId, noteId){
  await apiSend(`${API.tasks}${taskId}/notes/${noteId}/`, 'DELETE', null);
  await loadNotes(taskId);
}
window.deleteNote = deleteNote;

/* Next actions */
async function loadActions(taskId){
  const listEl = document.getElementById('actions-list-' + taskId);
  if(!listEl) return;

  listEl.innerHTML = '';
  const res = await apiGet(`${API.tasks}${taskId}/actions/`);
  const items = res.results || res || [];

  if(!items.length){
    listEl.innerHTML = `<li class="text-muted small">No next actions yet.</li>`;
    return;
  }

  items.forEach(a => listEl.appendChild(renderActionItem(taskId, a)));
}

function renderActionItem(taskId, a){
  const li = document.createElement('li');
  li.className = 'd-flex align-items-center justify-content-between gap-2 mb-1';

  const title = (a && (a.title ?? a.text ?? '')).toString();
  const completed = !!(a && (a.completed ?? a.done));

  li.innerHTML = `
    <label class="d-flex align-items-center gap-2 flex-grow-1 small m-0">
      <input type="checkbox" ${completed ? 'checked' : ''} onchange="toggleAction('${taskId}','${a.id}', this.checked)">
      <span class="${completed ? 'text-decoration-line-through text-muted' : ''}">${esc(title)}</span>
    </label>
    <button class="btn btn-plain btn-sm" onclick="deleteAction('${taskId}','${a.id}')">Delete</button>
  `;
  return li;
}

async function toggleAction(taskId, actionId, completed){
  await apiSend(`${API.tasks}${taskId}/actions/${actionId}/`, 'PATCH', { completed });
  await loadActions(taskId);
}
window.toggleAction = toggleAction;


async function addAction(taskId){
  const input = document.getElementById('new-action-' + taskId);
  const title = (input?.value || '').trim();
  if(!title) return;

  await apiSend(`${API.tasks}${taskId}/actions/`, 'POST', { title });

  if(input) input.value = '';
  await loadActions(taskId);
}
window.addAction = addAction;


async function deleteAction(taskId, actionId){
  await apiSend(`${API.tasks}${taskId}/actions/${actionId}/`, 'DELETE', null);
  await loadActions(taskId);
}
window.deleteAction = deleteAction;

/* Folder edit and delete stubs, keep your existing behavior if you already had these in template */
async function deleteFolder(folderId){
  await apiSend(`${API.folders}${folderId}/`, 'DELETE', null);
  await renderSidebar();
  await showInbox();
}
window.deleteFolder = deleteFolder;

async function deleteSpace(spaceId){
  await apiSend(`${API.spaces}${spaceId}/`, 'DELETE', null);
  await renderSidebar();
  await showInbox();
}
window.deleteSpace = deleteSpace;

function startEditFolder(folderId){
  alert('Edit folder UI not moved yet. If you want, tell me your current edit flow and I will wire it here.');
}
window.startEditFolder = startEditFolder;

function startEditSpace(spaceId){
  alert('Edit space UI not moved yet. If you want, tell me your current edit flow and I will wire it here.');
}
window.startEditSpace = startEditSpace;

function fmtTodayLabel(){
  return fmtUIDate(new Date());
}

document.addEventListener('click', function(e){
  const header = e.target.closest('.task-toggle');
  if(!header) return;

  const taskId = header.dataset.taskId;
  if(!taskId) return;

  openDetails(taskId);
});
