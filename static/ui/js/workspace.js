/* Finy Workspace JS
   Kept in one file for now. Split later once stable.
*/

'use strict';

/* API endpoints */
const API = (window.FINY && window.FINY.api) ? window.FINY.api : {
  folders: '/api/folders/',
  spaces: '/api/spaces/',
  tasks: '/api/tasks/',
  quickAdd: '/api/tasks/quick-add/',
  priority: '/api/tasks/priority/',
  today: '/api/tasks/today/',
  upcoming: '/api/tasks/upcoming/',
  spaceCategories: '/api/space-categories/',
  plannedRange: '/api/tasks/planned-range/',
  counts: '/api/tasks/counts/',
  overdue: '/api/tasks/overdue/',
};

function csrftoken(){ return document.getElementById('csrf')?.value || ''; }
function esc(s){ return (s||'').replace(/[&<>"']/g,m=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])); }

function sortPinnedFirst(items){
  return (items || []).slice().sort((a,b) => {
    const pinnedDelta = (b.is_pinned ? 1 : 0) - (a.is_pinned ? 1 : 0);
    if(pinnedDelta) return pinnedDelta;
    return String(a.name || '').localeCompare(String(b.name || ''));
  });
}

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

function fmtEstimateLabel(mins){
  const m = Number(mins || 0);
  if(!m) return '';
  if(m === 10) return '10 mins';
  if(m === 30) return '30 mins';
  if(m === 60) return '1 hour';
  if(m === 120) return '2 hours';
  if(m === 240) return '4 hours';
  if(m === 360) return '6 hours';
  if(m === 361) return '+6 hours';
  return `${m} mins`;
}

function buildEstimateSelectHtml(taskId, selectedValue){
  const options = [
    ['', 'No estimate'],
    [10, '10 mins'],
    [30, '30 mins'],
    [60, '1 hour'],
    [120, '2 hours'],
    [240, '4 hours'],
    [360, '6 hours'],
    [361, '+6 hours'],
  ];

  return `
    <select class="form-select form-select-sm" id="est-${taskId}">
      ${options.map(([value, label]) => {
        const selected = String(value) === String(selectedValue || '') ? 'selected' : '';
        return `<option value="${value}" ${selected}>${label}</option>`;
      }).join('')}
    </select>
  `;
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

function updateWorkspaceBadge(achievement){
  if(!achievement) return;

  const strip = document.getElementById('workspaceBadgeStrip');
  const badge = document.getElementById('workspaceCurrentBadge');
  const icon = document.getElementById('workspaceBadgeIcon');
  const fallback = document.getElementById('workspaceBadgeFallback');
  const name = document.getElementById('workspaceBadgeName');

  if(!strip || !badge || !icon || !fallback || !name) return;

  strip.classList.remove('d-none');
  badge.classList.remove('badge-image-missing');
  badge.title = achievement.name || '';
  name.textContent = achievement.name || '';
  fallback.textContent = (achievement.name || '').charAt(0);

  if(achievement.badge_url){
    badge.classList.add('has-badge-image');
    icon.src = achievement.badge_url;
    icon.alt = achievement.name || '';
    icon.classList.remove('d-none');
  } else {
    badge.classList.remove('has-badge-image');
    icon.removeAttribute('src');
    icon.alt = '';
    icon.classList.add('d-none');
  }
}

async function markWorkspaceAchievementSeen(achievementId){
  if(!achievementId || !API.achievementSeen) return;
  await apiSend(`${API.achievementSeen}${achievementId}/seen/`, 'POST', {});
}

function showWorkspaceAchievementModal(achievement){
  const modalEl = document.getElementById('workspaceAchievementModal');
  const badge = document.getElementById('workspaceAchievementBadge');
  const title = document.getElementById('workspaceAchievementName');
  const message = document.getElementById('workspaceAchievementMessage');
  const button = document.getElementById('workspaceAchievementContinue');

  if(!modalEl || !title || !message || !button) return;

  title.textContent = achievement.name || '';
  message.textContent = achievement.message || '';

  if(badge){
    if(achievement.badge_url){
      badge.src = achievement.badge_url;
      badge.alt = achievement.name || '';
      badge.classList.remove('d-none');
    } else {
      badge.removeAttribute('src');
      badge.alt = '';
      badge.classList.add('d-none');
    }
  }

  const modal = window.bootstrap
    ? window.bootstrap.Modal.getOrCreateInstance(modalEl)
    : null;

  const onContinue = async () => {
    button.removeEventListener('click', onContinue);
    await markWorkspaceAchievementSeen(achievement.id);
    if(modal) modal.hide();
  };

  button.addEventListener('click', onContinue);

  if(modal){
    modal.show();
  }
}

async function refreshWorkspaceAchievements(){
  if(!API.achievementStatus) return;

  let status = null;

  try{
    status = await apiGet(API.achievementStatus);
  }catch(e){
    return;
  }

  if(status.highest){
    updateWorkspaceBadge(status.highest);
  }

  if(status.unseen){
    showWorkspaceAchievementModal(status.unseen);
  }
}

/* State */
let inboxId = null;
let foldersCache = null;
let spacesCache = null;
let categoriesCache = null;
let activeFilter = { type:'inbox', id:null, name:'INBOX' };

const els = {
  list: document.getElementById('task-list'),
  newTaskForm: document.getElementById('new-task-form'),
  newTaskTitle: document.getElementById('nt-title'),
  inboxBadge: document.getElementById('inbox-count-badge'),
  listTitle: document.getElementById('list-title'),
  listHelperText: document.getElementById('list-helper-text'),
  contextQuickAdd: document.getElementById('context-quick-add'),
  globalSearchForm: document.getElementById('global-search-form'),
  globalSearchInput: document.getElementById('global-search-input'),
  clearSearchBtn: document.getElementById('clear-search-btn'),
  taskFilterBar: document.getElementById('task-filter-bar'),
  filterSpaceWrap: document.getElementById('filter-space-wrap'),
  filterFolderWrap: document.getElementById('filter-folder-wrap'),
  filterSpace: document.getElementById('filter-space'),
  filterFolder: document.getElementById('filter-folder'),
  filterSort: document.getElementById('filter-sort'),
  applyTaskFilters: document.getElementById('apply-task-filters'),
  clearTaskFilters: document.getElementById('clear-task-filters')

};

/* Calendar state and elements */
let activeView = 'list';
let calDays =7;
let calStart = null;
let myDaySort = 'due_date';
let myDayFilterSpaceId = '';
let calendarTasksByDay = {};
let calendarRenderedStart = null;
let calendarRenderedToday = null;

const calEls = {
  listView: document.getElementById('list-view'),
  calView: document.getElementById('calendar-view'),
  calList: document.getElementById('calendar-list'),
  calTitle: document.getElementById('calendar-title'),
  calPrev: document.getElementById('calPrev'),
  calNext: document.getElementById('calNext'),
  calBack: document.getElementById('calBackToList'),
  filter: document.getElementById('my-day-filter'),
  sort: document.getElementById('my-day-sort')
};

window.addEventListener('DOMContentLoaded', init);

async function init(){
  loadMyDaySortPreference();
  wireButtons();
  await loadCategories();
  await resolveInbox();
  await renderSidebar();
  await refreshWorkspaceAchievements();
  await showCalendar();
}


function toggleDueDateForRepeat(taskId){
  const repeat = document.getElementById('repeat-' + taskId)?.value || '';
  const dueInput = document.getElementById('due-' + taskId);

  if(!dueInput) return;

  if(repeat){
    dueInput.value = '';
    dueInput.disabled = true;
  } else {
    dueInput.disabled = false;
  }
}
window.toggleDueDateForRepeat = toggleDueDateForRepeat;


function wireButtons(){
  document.getElementById('showAddFolder')?.addEventListener('click', () => {
    document.getElementById('addFolderRow')?.classList.remove('d-none');
    document.getElementById('newFolderName')?.focus();
  });

  document.getElementById('showAddSpace')?.addEventListener('click', () => {
    document.getElementById('addSpaceRow')?.classList.remove('d-none');
    document.getElementById('newSpaceName')?.focus();
  });

  document.getElementById('btnAllTasks')?.addEventListener('click', showAllTasks);
  document.getElementById('btnInbox')?.addEventListener('click', showInbox);
  document.getElementById('btnOverdue')?.addEventListener('click', showOverdue);
  document.getElementById('btnPriority')?.addEventListener('click', showPriority);
  document.getElementById('btnCompleted')?.addEventListener('click', showCompleted);

  document.getElementById('btnCalendar')?.addEventListener('click', showCalendar);
  calEls.calPrev?.addEventListener('click', () => shiftCalendar(-calDays));
  calEls.calNext?.addEventListener('click', () => shiftCalendar(calDays));
  calEls.calBack?.addEventListener('click', () => showListView());
  calEls.filter?.addEventListener('change', () => {
    myDayFilterSpaceId = calEls.filter.value || '';
    renderCalendarSections();
  });
  calEls.sort?.addEventListener('change', () => {
    setMyDaySortPreference(calEls.sort.value);
    renderCalendarSections();
  });

  els.newTaskForm?.addEventListener('submit', onCreateSubmit);
  els.globalSearchForm?.addEventListener('submit', onGlobalSearchSubmit);
  els.clearSearchBtn?.addEventListener('click', clearGlobalSearch);
  els.applyTaskFilters?.addEventListener('click', applyTaskFilters);
  els.clearTaskFilters?.addEventListener('click', clearTaskFilters);
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
  const start = startOfDay(center);
  const end = startOfDay(addDays(center, 6));

  const startISO = toISODate(start);
  const endISO = toISODate(end);

  if(calEls.calTitle){
    calEls.calTitle.textContent = `My Day ${fmtUIDate(start)} to ${fmtUIDate(end)}`;
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

  calendarTasksByDay = byDay;
  calendarRenderedStart = start;
  calendarRenderedToday = today;
  populateMyDayFilterOptions();
  renderCalendarSections();
}

function populateMyDayFilterOptions(){
  if(!calEls.filter) return;

  const tasks = Object.values(calendarTasksByDay).flat();
  const options = getCalendarDaySpaceOptions(tasks);
  const selectedSpace = (spacesCache || []).find(
    space => String(space.id) === String(myDayFilterSpaceId)
  );

  if(
    selectedSpace
    && !options.some(space => String(space.id) === String(selectedSpace.id))
  ){
    options.push(selectedSpace);
    options.sort(
      (a, b) => String(a.name || '').localeCompare(String(b.name || ''))
    );
  }

  calEls.filter.innerHTML = `
    <option value="">All spaces</option>
    ${options.map(space => `
      <option value="${space.id}" ${String(space.id) === String(myDayFilterSpaceId) ? 'selected' : ''}>
        ${esc(space.name)}
      </option>
    `).join('')}
  `;
  calEls.filter.value = myDayFilterSpaceId;
}

function renderCalendarSections(){
  if(!calEls.calList || !calendarRenderedStart || !calendarRenderedToday) return;
  calEls.calList.innerHTML = '';
  for(let i = 0; i <= 6; i++){
    const d = startOfDay(addDays(calendarRenderedStart, i));
    const iso = toISODate(d);
    const dayTasks = calendarTasksByDay[iso] || [];

    calEls.calList.appendChild(
      buildCalendarSection(d, dayTasks, calendarRenderedToday)
    );
  }
}

function myDaySortStorageKey(){
  const userId = String(window.FINY?.userId || '').trim();
  return userId ? `finy.myDaySort.${userId}` : '';
}

function normaliseMyDaySort(value){
  return value === 'quickest' || value === 'due_date'
    ? value
    : 'due_date';
}

function loadMyDaySortPreference(){
  const key = myDaySortStorageKey();
  let saved = 'due_date';
  if(key){
    try{
      saved = window.localStorage.getItem(key) || 'due_date';
    }catch(error){}
  }
  myDaySort = normaliseMyDaySort(saved);
  if(calEls.sort) calEls.sort.value = myDaySort;
}

function setMyDaySortPreference(value){
  myDaySort = normaliseMyDaySort(value);
  if(calEls.sort) calEls.sort.value = myDaySort;

  const key = myDaySortStorageKey();
  if(key){
    try{
      window.localStorage.setItem(key, myDaySort);
    }catch(error){}
  }
}

function hasEstimate(task){
  return task.estimated_minutes !== null
    && task.estimated_minutes !== undefined
    && task.estimated_minutes !== '';
}

function compareOptionalDueDate(a, b){
  const aDue = a.due_date || '';
  const bDue = b.due_date || '';
  if(!!aDue !== !!bDue) return aDue ? -1 : 1;
  if(aDue !== bDue) return aDue.localeCompare(bDue);
  return 0;
}

function compareOptionalEstimate(a, b){
  const aHasEstimate = hasEstimate(a);
  const bHasEstimate = hasEstimate(b);
  if(aHasEstimate !== bHasEstimate) return aHasEstimate ? -1 : 1;
  if(aHasEstimate && Number(a.estimated_minutes) !== Number(b.estimated_minutes)){
    return Number(a.estimated_minutes) - Number(b.estimated_minutes);
  }
  return 0;
}

function compareMyDayTasks(a, b, sortValue=myDaySort){
  let comparison = 0;
  if(sortValue === 'quickest'){
    comparison = compareOptionalEstimate(a, b);
    if(!comparison) comparison = compareOptionalDueDate(a, b);
  }else{
    comparison = compareOptionalDueDate(a, b);
    if(!comparison) comparison = compareOptionalEstimate(a, b);
  }

  if(comparison) return comparison;
  return Number(a.id) - Number(b.id);
}

function buildCalendarSectionLegacy(dateObj, tasks, today){
  const section = document.createElement('section');
  section.className = 'calendar-section';

  const heading = document.createElement('div');
  heading.className = 'calendar-section-header';

  let label = fmtDayHeader(dateObj);

  const dayTime = startOfDay(dateObj).getTime();
  const todayTime = startOfDay(today).getTime();

  if(dayTime < todayTime){
    label = `Past ${fmtDayHeader(dateObj)}`;
  }else if(dayTime === todayTime){
    label = `Today ${fmtDayHeader(dateObj)}`;
  }else if(dayTime === startOfDay(addDays(today, 1)).getTime()){
    label = `Tomorrow ${fmtDayHeader(dateObj)}`;
  }

  const total = (tasks || []).reduce((sum, t) => sum + (t.estimated_minutes ? Number(t.estimated_minutes) : 0), 0);

  heading.innerHTML = `
    <div>
      <h3 class="calendar-section-title">${esc(label)}</h3>
      <div class="calendar-section-sub">${tasks.length} tasks, ${esc(fmtMinutesHuman(total))}</div>
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


function buildCalendarSection(dateObj, tasks, today){
  const section = document.createElement('section');
  section.className = 'calendar-section';

  const heading = document.createElement('div');
  heading.className = 'calendar-section-header';

  let label = fmtDayHeader(dateObj);

  const dayTime = startOfDay(dateObj).getTime();
  const todayTime = startOfDay(today).getTime();

  if(dayTime < todayTime){
    label = `Past ${fmtDayHeader(dateObj)}`;
  }else if(dayTime === todayTime){
    label = `Today ${fmtDayHeader(dateObj)}`;
  }else if(dayTime === startOfDay(addDays(today, 1)).getTime()){
    label = `Tomorrow ${fmtDayHeader(dateObj)}`;
  }

  const body = document.createElement('div');
  body.className = 'calendar-section-body';

  const dayTasks = tasks || [];
  const sectionDate = toISODate(dateObj);
  const isToday = sectionDate === toISODate(today);

  function renderDayTasks(){
    const filteredTasks = (myDayFilterSpaceId
      ? dayTasks.filter(
          t => Array.isArray(t.spaces)
            && t.spaces.map(String).includes(String(myDayFilterSpaceId))
        )
      : dayTasks.slice()
    ).sort((a, b) => compareMyDayTasks(a, b));

    const total = filteredTasks.reduce(
      (sum, t) => sum + (t.estimated_minutes ? Number(t.estimated_minutes) : 0),
      0
    );

    heading.innerHTML = `
      <div class="calendar-section-heading-main">
        <h3 class="calendar-section-title">${esc(label)}</h3>
        <div class="calendar-section-sub">${filteredTasks.length} tasks, ${esc(fmtMinutesHuman(total))}</div>
      </div>
    `;

    body.innerHTML = '';

    if(!filteredTasks.length){
      body.innerHTML = myDayFilterSpaceId
        ? `<div class="text-muted small">No tasks for this space.</div>`
        : `<div class="text-muted small">No planned tasks.</div>`;
    }else{
      filteredTasks.forEach(t => body.appendChild(buildTaskCard(t)));
    }

  }

  renderDayTasks();

  section.appendChild(heading);
  section.appendChild(buildQuickAddElement({
    id: `calendar-${sectionDate}`,
    label: `Add a task for ${label}`,
    placeholder: isToday
      ? 'Add a task for today'
      : `Add a task for ${fmtUIDate(dateObj)}`,
    payload: {
      context_type: isToday ? 'my_day' : 'date',
      planned_date: sectionDate,
    },
    onCreated: async task => {
      dayTasks.push(task);
      renderDayTasks();
      await renderSidebar();
      await refreshWorkspaceAchievements();
      return myDayFilterSpaceId
        ? 'Task added. Clear the space filter to see it.'
        : '';
    },
  }));
  section.appendChild(body);
  return section;
}

function getCalendarDaySpaceOptions(tasks){
  const ids = new Set();

  (tasks || []).forEach(t => {
    (t.spaces || []).forEach(spaceId => ids.add(String(spaceId)));
  });

  return (spacesCache || [])
    .filter(space => ids.has(String(space.id)))
    .sort((a,b) => String(a.name || '').localeCompare(String(b.name || '')));
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

  const folders = sortPinnedFirst(foldersCache.filter(f => !f.is_inbox));
    let taskCounts = {
    inbox: 0,
    completed: 0,
    priority: 0,
    folders: {},
    spaces: {}
    };

    try{
      taskCounts = await apiGet(API.counts);
    }catch(e){}

const folderCounts = taskCounts.folders || {};

  const folderList = document.getElementById('folderList');
  if(folderList){
    folderList.innerHTML = folders.map(f => (
      `<li class="list-group-item d-flex align-items-center" data-id="${f.id}">
        <button class="btn btn-link btn-sm text-decoration-none text-reset list-title-btn" onclick="filterByFolder('${f.id}')">${esc(f.name)}</button>
        ${f.is_pinned ? '<span class="badge pinned-badge me-2">Pinned</span>' : ''}
        <span id="folder-count-${f.id}" class="badge rounded-pill count-badge me-2">${folderCounts[f.id] ?? 0}</span>
        <div class="dropdown kebab">
          <button class="btn btn-plain btn-sm btn-kebab" data-bs-toggle="dropdown" aria-expanded="false" aria-label="Folder actions">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/></svg>
          </button>
          <ul class="dropdown-menu dropdown-menu-end">
            <li><button class="dropdown-item" onclick="toggleFolderPin('${f.id}')">${f.is_pinned ? 'Unpin' : 'Pin'}</button></li>
            <li><button class="dropdown-item" onclick="startEditFolder('${f.id}')">Edit</button></li>
            <li><button class="dropdown-item text-danger" onclick="deleteFolder('${f.id}')">Delete</button></li>
          </ul>
        </div>
      </li>`
    )).join('');
  }

  const spaces = sortPinnedFirst(spacesCache || []);
  const spaceCounts = taskCounts.spaces || {};

  const spaceList = document.getElementById('spaceList');
  if(spaceList){
    spaceList.innerHTML = spaces.map(s => (
      `<li class="list-group-item d-flex align-items-center" data-id="${s.id}">
        <button class="btn btn-link btn-sm text-decoration-none text-reset list-title-btn" onclick="filterBySpace('${s.id}')">${esc(s.name)}</button>
        ${s.is_pinned ? '<span class="badge pinned-badge me-2">Pinned</span>' : ''}
        <span id="space-count-${s.id}" class="badge rounded-pill count-badge me-2">${spaceCounts[s.id] ?? 0}</span>
        <div class="dropdown kebab">
          <button class="btn btn-plain btn-sm btn-kebab" data-bs-toggle="dropdown" aria-expanded="false" aria-label="Space actions">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/></svg>
          </button>
          <ul class="dropdown-menu dropdown-menu-end">
            <li><button class="dropdown-item" onclick="toggleSpacePin('${s.id}')">${s.is_pinned ? 'Unpin' : 'Pin'}</button></li>
            ${String(s.name || '').toLowerCase() === 'waiting_for' ? '' : `
              <li><button class="dropdown-item" onclick="startEditSpace('${s.id}')">Edit</button></li>
              <li><button class="dropdown-item text-danger" onclick="deleteSpace('${s.id}')">Delete</button></li>
            `}
          </ul>
        </div>
      </li>`
    )).join('');
  }

  const allTasksBadge = document.getElementById('all-tasks-count-badge');
  if(allTasksBadge){
    allTasksBadge.textContent = String(taskCounts.all || 0);
  }

  const myDayBadge = document.getElementById('my-day-count-badge');
  if(myDayBadge){
    myDayBadge.textContent = String(taskCounts.my_day || 0);
  }

  if(els.inboxBadge){
    els.inboxBadge.textContent = String(taskCounts.inbox || 0);
  }

  const completedBadge = document.getElementById('completed-count-badge');
  if(completedBadge){
    completedBadge.textContent = String(taskCounts.completed || 0);
  }

  const priorityBadge = document.getElementById('priority-count-badge');
  if(priorityBadge){
    priorityBadge.textContent = String(taskCounts.priority || 0);
  }

  const overdueBadge = document.getElementById('overdue-count-badge');
  if(overdueBadge){
    overdueBadge.textContent = String(taskCounts.overdue || 0);
  }


}

/* Filters */


async function onGlobalSearchSubmit(e){
  e.preventDefault();

  const query = (els.globalSearchInput?.value || '').trim();

  if(!query){
    await showCalendar();
    return;
  }

  showListView();

  activeFilter = {
    type: 'search',
    id: null,
    name: `Search: ${query}`,
    query: query
  };

  await renderListByFilter();
}

async function clearGlobalSearch(){
  if(els.globalSearchInput){
    els.globalSearchInput.value = '';
  }

  await showCalendar();
}

function resetTaskFilterControls(){
  if(els.filterSpace) els.filterSpace.value = '';
  if(els.filterFolder) els.filterFolder.value = '';
  if(els.filterSort) els.filterSort.value = 'planned_date';
}

function populateTaskFilterControls(){
  if(els.filterSpace){
    const usedSpaceIds = new Set();

    (window.currentTasks || []).forEach(t => {
      (t.spaces || []).forEach(sid => usedSpaceIds.add(String(sid)));
    });

    const spaces = (spacesCache || [])
      .filter(s => usedSpaceIds.has(String(s.id)))
      .sort((a,b)=>a.name.localeCompare(b.name));

    els.filterSpace.innerHTML =
      '<option value="">All spaces</option>' +
      spaces.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join('');
  }

  if(els.filterFolder){
    const usedFolderIds = new Set();

    (window.currentTasks || []).forEach(t => {
      if(t.folder) usedFolderIds.add(String(t.folder));
    });

    const folders = (foldersCache || [])
      .filter(f => usedFolderIds.has(String(f.id)))
      .sort((a,b)=>a.name.localeCompare(b.name));
    els.filterFolder.innerHTML =
      '<option value="">All folders</option>' +
      folders.map(f => `<option value="${f.id}">${esc(f.name)}</option>`).join('');
  }
}

    function updateTaskFilterBar(){
      if(!els.taskFilterBar) return;

      const isFolder = activeFilter?.type === 'folder';
      const isSpace = activeFilter?.type === 'space';
      const isOverdue = activeFilter?.type === 'overdue';
      const isPriority = activeFilter?.type === 'priority';
      const isAll = activeFilter?.type === 'all';

      if(!isFolder && !isSpace && !isOverdue && !isPriority && !isAll){
        els.taskFilterBar.classList.add('d-none');
        return;
      }

      populateTaskFilterControls();

      els.taskFilterBar.classList.remove('d-none');

      if(els.filterSpaceWrap){
        els.filterSpaceWrap.classList.toggle('d-none', !(isFolder || isOverdue || isPriority || isAll));
      }

      if(els.filterFolderWrap){
        els.filterFolderWrap.classList.toggle('d-none', !(isSpace || isOverdue || isPriority || isAll));
      }
    }

  async function applyTaskFilters(){
    if(!activeFilter || !['all', 'folder', 'space', 'overdue', 'priority'].includes(activeFilter.type)) return;

    activeFilter.extra = {
      space: els.filterSpace?.value || '',
      folder: els.filterFolder?.value || '',
      ordering: els.filterSort?.value || 'planned_date'
    };

    await renderListByFilter();
  }

  async function clearTaskFilters(){
    if(!activeFilter || !['all', 'folder', 'space', 'overdue', 'priority'].includes(activeFilter.type)) return;

    activeFilter.extra = {
      space: '',
      folder: '',
      ordering: 'planned_date'
    };

    resetTaskFilterControls();

    await renderListByFilter();
  }

  async function filterByFolder(folderId){
    showListView();
    const f = (foldersCache || []).find(x => String(x.id) === String(folderId));
    activeFilter = {
      type:'folder',
      id: parseInt(folderId,10),
      name: f ? f.name : 'Folder',
      extra: { space: '', folder: '', ordering: 'planned_date' }
    };
    await renderListByFilter();
    jumpToWorkspaceMain();
  }
  window.filterByFolder = filterByFolder;

  async function filterBySpace(spaceId){
    showListView();

    const s = (spacesCache || []).find(x => String(x.id) === String(spaceId));

    activeFilter = {
      type:'space',
      id: parseInt(spaceId,10),
      name: s ? s.name : 'Space',
      extra: { space: '', folder: '', plannedDate: '', ordering: 'planned_date' }
    };

    await renderListByFilter();
    jumpToWorkspaceMain();
  }

  window.filterBySpace = filterBySpace;

  async function showAllTasks(){
    showListView();
    activeFilter = {
      type:'all',
      id:null,
      name:'All Tasks',
      extra: { space: '', folder: '', ordering: 'planned_date' }
    };
    await renderListByFilter();
    jumpToWorkspaceMain();
  }

  async function showInbox(){
    showListView();
    activeFilter = { type:'inbox', id: inboxId, name:'INBOX' };
    await renderListByFilter();
    jumpToWorkspaceMain();
  }
  async function showOverdue(){
    showListView();
    activeFilter = {
      type:'overdue',
      id:null,
      name:'Overdue',
      extra: { space: '', folder: '', ordering: 'due_date' }
    };
    await renderListByFilter();
    jumpToWorkspaceMain();
  }

    async function showPriority(){
      showListView();
      activeFilter = {
        type:'priority',
        id:null,
        name:'Needs Attention',
        extra: { space: '', folder: '', ordering: 'planned_date' }
      };
      await renderListByFilter();
      jumpToWorkspaceMain();
    }

  async function showCompleted(){
    showListView();
    activeFilter = { type:'completed', id:null, name:'Completed Tasks' };
    await renderListByFilter();
    jumpToWorkspaceMain();
  }


/* New task */
function quickAddRequestId(){
  if(window.crypto && typeof window.crypto.randomUUID === 'function'){
    return window.crypto.randomUUID().replace(/-/g, '');
  }
  return `qa${Date.now()}${Math.random().toString(36).slice(2)}`;
}

function buildQuickAddElement({ id, label, placeholder, payload, onCreated }){
  const wrap = document.createElement('div');
  wrap.className = 'context-quick-add';
  wrap.innerHTML = `
    <form class="context-quick-add-form" novalidate>
      <label class="visually-hidden" for="quick-add-${esc(id)}">${esc(label)}</label>
      <input
        id="quick-add-${esc(id)}"
        class="form-control form-control-sm context-quick-add-input"
        type="text"
        maxlength="255"
        autocomplete="off"
        placeholder="${esc(placeholder)}"
      >
      <button class="btn btn-plain btn-sm context-quick-add-button" type="submit">Add</button>
    </form>
    <div class="context-quick-add-feedback small" role="status" aria-live="polite"></div>
  `;

  const form = wrap.querySelector('form');
  const input = wrap.querySelector('input');
  const button = wrap.querySelector('button');
  const feedback = wrap.querySelector('.context-quick-add-feedback');

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if(form.dataset.submitting === 'true') return;

    const title = (input.value || '').trim();
    if(!title) return;

    form.dataset.submitting = 'true';
    input.disabled = true;
    button.disabled = true;
    feedback.textContent = '';
    feedback.classList.remove('text-danger', 'text-success');

    try{
      const task = await apiSend(API.quickAdd, 'POST', {
        ...payload,
        title,
        client_request_id: quickAddRequestId(),
      });
      input.value = '';
      const successMessage = await onCreated(task);
      const currentInput = document.getElementById(`quick-add-${id}`);
      const currentFeedback = currentInput
        ?.closest('.context-quick-add')
        ?.querySelector('.context-quick-add-feedback');
      if(currentFeedback && successMessage){
        currentFeedback.textContent = successMessage;
        currentFeedback.classList.add('text-success');
      }
      currentInput?.focus();
    }catch(error){
      feedback.textContent = 'Could not add this task. Please try again.';
      feedback.classList.add('text-danger');
    }finally{
      form.dataset.submitting = 'false';
      input.disabled = false;
      button.disabled = false;
    }
  });

  return wrap;
}

function renderContextQuickAdd(){
  if(!els.contextQuickAdd) return;
  els.contextQuickAdd.innerHTML = '';

  let config = null;
  if(activeFilter?.type === 'inbox'){
    config = {
      id: 'inbox',
      label: 'Add a task to Inbox',
      placeholder: 'Add a task to Inbox',
      payload: { context_type: 'inbox' },
    };
  }else if(activeFilter?.type === 'folder'){
    config = {
      id: `folder-${activeFilter.id}`,
      label: `Add a task to ${activeFilter.name}`,
      placeholder: `Add a task to ${activeFilter.name}`,
      payload: { context_type: 'folder', folder_id: activeFilter.id },
    };
  }else if(activeFilter?.type === 'space'){
    config = {
      id: `space-${activeFilter.id}`,
      label: `Add a task to ${activeFilter.name}`,
      placeholder: `Add a task to ${activeFilter.name}`,
      payload: { context_type: 'space', space_id: activeFilter.id },
    };
  }

  if(!config) return;

  els.contextQuickAdd.appendChild(buildQuickAddElement({
    ...config,
    onCreated: async () => {
      await renderListByFilter();
      await refreshWorkspaceAchievements();
      return '';
    },
  }));
}

async function onCreateSubmit(e){
  e.preventDefault();
  const title = (els.newTaskTitle.value || '').trim();
  if(!title) return;
  if(!inboxId){ alert('No Inbox found'); return; }
  await apiSend(API.tasks, 'POST', { title, folder: inboxId });
  els.newTaskTitle.value = '';
  await renderListByFilter();
  await renderSidebar();
  await refreshWorkspaceAchievements();
}

function refreshOpenFolderSelects(selectedFolderId){
  document.querySelectorAll('select[id^="folder-"]').forEach(select => {
    const currentValue = selectedFolderId ? String(selectedFolderId) : select.value;
    const folders = (foldersCache || []).slice().sort((a,b)=>a.name.localeCompare(b.name));

    select.innerHTML = folders.map(f => {
      const selected = String(f.id) === String(currentValue) ? 'selected' : '';
      return `<option value="${f.id}" ${selected}>${esc(f.name)}</option>`;
    }).join('');
  });
}

function refreshOpenSpacePanels(selectedSpaceId){
  document.querySelectorAll('[id^="spaces-panel-"]').forEach(panel => {
    const taskId = panel.id.replace('spaces-panel-', '');
    const checks = Array.from(document.querySelectorAll('.space-check-' + taskId));
    const selected = checks
      .filter(ch => ch.checked)
      .map(ch => String(ch.value));

    if(selectedSpaceId){
      selected.push(String(selectedSpaceId));
    }

    panel.innerHTML = buildSpacesChecklistHtml(taskId, [...new Set(selected)]);

    const summary = document.getElementById('spaces-summary-' + taskId);
    if(summary){
      summary.innerHTML = buildSpacesSummaryHtml([...new Set(selected)]);
    }
  });
}

/* Create folder or space */
async function createFolder(nameId, descId){
  const nameEl = document.getElementById(nameId);
  const descEl = descId ? document.getElementById(descId) : null;

  const name = (nameEl?.value || '').trim();
  const description = (descEl?.value || '').trim();
  if(!name) return;

  const folder = await apiSend(API.folders, 'POST', { name, description });

  if(folder && folder.id){
    foldersCache = (foldersCache || []).filter(f => String(f.id) !== String(folder.id));
    foldersCache.push(folder);
    refreshOpenFolderSelects(folder.id);
  }

  if(nameEl) nameEl.value = '';
  if(descEl) descEl.value = '';

  document.getElementById('addFolderRow')?.classList.add('d-none');

  const quickCreateDropdown = document.querySelector('.topbar-btn-quick')?.closest('.dropdown');
  const dropdownToggle = quickCreateDropdown?.querySelector('[data-bs-toggle="dropdown"]');

  if(dropdownToggle && window.bootstrap){
    const dropdown = window.bootstrap.Dropdown.getOrCreateInstance(dropdownToggle);
    dropdown.hide();
  }

  await renderSidebar();
  await refreshWorkspaceAchievements();
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

  const space = await apiSend(API.spaces, 'POST', { name, category });

  if(space && space.id){
    spacesCache = (spacesCache || []).filter(s => String(s.id) !== String(space.id));
    spacesCache.push(space);
    refreshOpenSpacePanels(space.id);
  }

  if(nameEl) nameEl.value = '';
  document.getElementById('addSpaceRow')?.classList.add('d-none');
  document.getElementById('quickCreateError')?.classList.add('d-none');
  document.getElementById('spaceCreateError')?.classList.add('d-none');
  await renderSidebar();
  await refreshWorkspaceAchievements();
}
window.createSpace = createSpace;


function getHelperTextForFilter(){
  if(!activeFilter) return 'These are your tasks.';

  if(activeFilter.type === 'all'){
    return 'These are all your active tasks that still need to be completed.';
  }

  if(activeFilter.type === 'priority'){
    return 'These tasks were planned for today or earlier and still need a decision or action.';
  }

  if(activeFilter.type === 'overdue'){
    return 'These tasks have passed their due date and require urgent attention.';
  }

  if(activeFilter.type === 'inbox'){
    return 'These are unprocessed tasks. Review them, assign folders, spaces and dates, then move them into your system.';
  }

  if(activeFilter.type === 'completed'){
    return 'These are tasks you have completed.';
  }

  if(activeFilter.type === 'folder'){
    return 'These are active tasks in this folder. Use spaces, dates and sorting to decide what to work on next.';
  }

  if(activeFilter.type === 'space'){
    return 'These are active tasks linked to this space. This helps you focus on what you can do in this context.';
  }

  if(activeFilter.type === 'search'){
    return 'These are tasks matching your search.';
  }

  return 'These are your tasks.';
}

/* List rendering */
function applyClientTaskFilters(tasks){
  const extra = activeFilter?.extra || {};
  let filtered = Array.isArray(tasks) ? tasks.slice() : [];

  if(extra.space){
    filtered = filtered.filter(t =>
      Array.isArray(t.spaces) && t.spaces.map(String).includes(String(extra.space))
    );
  }

  if(extra.folder){
    filtered = filtered.filter(t =>
      String(t.folder || '') === String(extra.folder)
    );
  }

  const ordering = extra.ordering || '';

  filtered.sort((a, b) => {
    if(ordering === 'estimated_minutes'){
      const av = a.estimated_minutes || Number.POSITIVE_INFINITY;
      const bv = b.estimated_minutes || Number.POSITIVE_INFINITY;
      return av - bv;
    }

    if(ordering === 'due_date'){
      const av = a.due_date || '9999-12-31';
      const bv = b.due_date || '9999-12-31';
      return av.localeCompare(bv);
    }

    const av = a.planned_date || '9999-12-31';
    const bv = b.planned_date || '9999-12-31';
    return av.localeCompare(bv);
  });

  return filtered;
}



async function renderListByFilter(){
  showListView();

  if(els.listTitle){
    els.listTitle.textContent = activeFilter?.name || 'Tasks';
  }

  if(els.listHelperText){
    els.listHelperText.textContent = getHelperTextForFilter();
  }

  renderContextQuickAdd();
  updateTaskFilterBar();

  let res;

  if(activeFilter.type === 'all'){
    res = await apiGet(`${API.tasks}?completed=false&ordering=planned_date`);
  } else if(activeFilter.type === 'inbox'){
    res = await apiGet(`${API.tasks}?folder=${inboxId}&completed=false&ordering=due_date`);
  } else if(activeFilter.type === 'overdue'){
    res = await apiGet(API.overdue);
  } else if(activeFilter.type === 'priority'){
    res = await apiGet(API.priority);
  } else if(activeFilter.type === 'folder'){
    const extra = activeFilter.extra || {};
    const params = new URLSearchParams();

    params.set('folder', activeFilter.id);
    params.set('completed', 'false');

    if(extra.space) params.set('spaces', extra.space);

    params.set('ordering', extra.ordering || 'planned_date');

    res = await apiGet(`${API.tasks}?${params.toString()}`);
  } else if(activeFilter.type === 'space'){
    const extra = activeFilter.extra || {};
    const params = new URLSearchParams();

    params.set('spaces', activeFilter.id);
    params.set('completed', 'false');

    if(extra.folder) params.set('folder', extra.folder);

    params.set('ordering', extra.ordering || 'planned_date');

    res = await apiGet(`${API.tasks}?${params.toString()}`);
  } else if(activeFilter.type === 'completed'){
    res = await apiGet(`${API.tasks}?completed=true&ordering=-updated_at`);
  } else if(activeFilter.type === 'search'){
    const q = encodeURIComponent(activeFilter.query || '');
    res = await apiGet(`${API.tasks}?search=${q}&ordering=due_date`);
  } else {
    res = await apiGet(`${API.tasks}?completed=false&ordering=due_date`);
  }

  let tasks = Array.isArray(res) ? res : (res.results || res || []);

  if(activeFilter.type === 'completed'){
    tasks = tasks.filter(t => t.completed);
  }

  window.currentTasks = tasks;
  updateTaskFilterBar();

  if(['all', 'priority', 'overdue', 'folder', 'space'].includes(activeFilter.type)){
    tasks = applyClientTaskFilters(tasks);
  }

  renderTasks(tasks);
  await renderSidebar();
}

function jumpToWorkspaceMain(){
    const main = document.getElementById('workspaceMain');
    if(!main) return;

    main.scrollIntoView({
      behavior: 'smooth',
      block: 'start'
    });
  }

/* Task rendering */
function renderTasks(tasks){
  if(!els.list) return;
  els.list.innerHTML = '';

  if(!tasks.length){
    if(activeFilter?.type === 'search'){
      els.list.innerHTML = `<div class="text-muted small p-3">No tasks found for “${esc(activeFilter.query || '')}”.</div>`;
    } else {
      els.list.innerHTML = `<div class="text-muted small p-3">No tasks here yet.</div>`;
    }
    return;
  }

  tasks.forEach(t => els.list.appendChild(buildTaskCard(t)));
}


function buildTaskCard(t){
  const wrap = document.createElement('div');
  wrap.className = 'card task-card mb-2' + (t.completed ? ' task-completed' : '');

  const due = t.due_date ? fmtUIDateFromISO(t.due_date) : '';

  const todayIso = toISODate(new Date());

  let overdue = false;
  let dueToday = false;
  let priority = false;

  if(!t.completed){
    overdue = !!(t.due_date && t.due_date < todayIso);
    dueToday = !!(t.due_date && t.due_date === todayIso);
    priority = !!(t.planned_date && t.planned_date <= todayIso && !overdue);
  }

  const planned = t.planned_date ? fmtUIDateFromISO(t.planned_date) : '';
  const est = t.estimated_minutes ? fmtEstimateLabel(t.estimated_minutes) : '';
  const completedAt = t.completed_at ? fmtUIDateTimeFromISO(t.completed_at) : '';

  const folderName = (t.folder_name || '').trim();

  const folderHtml = t.folder && folderName ? `
    <span class="me-2 task-meta-link"
            onclick="event.stopPropagation(); filterByFolder('${t.folder}')">
      📁 ${esc(folderName)}
    </span>
  ` : '';

  const selectedSpaceIds = Array.isArray(t.spaces) ? t.spaces.map(x => String(x)) : [];

  const spacesHtml = selectedSpaceIds
    .map(spaceId => {
      const space = (spacesCache || []).find(s => String(s.id) === String(spaceId));
      if(!space) return '';
      return `
        <span class="me-2 task-meta-link"
                onclick="event.stopPropagation(); filterBySpace('${space.id}')">
          🏷️ ${esc(space.name)}
        </span>
      `;
    })
    .join('');

  wrap.innerHTML = `
    <div class="card-body">
      <div class="d-flex justify-content-between align-items-start gap-2 task-toggle" data-task-id="${t.id}">
        <div class="flex-grow-1">
          <div class="d-flex align-items-center gap-2">
          <input
            type="checkbox"
            class="task-complete-btn"
            ${t.completed ? 'checked' : ''}
            title="Mark complete"
            onclick="event.stopPropagation()"
            onchange="toggleComplete(${t.id})"
            >
            <h3 class="m-0 ${t.completed ? 'text-decoration-line-through text-muted' : ''}">
              ${esc(t.title)}
            </h3>

          </div>

          <div class="meta-icons mt-1">
            ${folderHtml}
            ${spacesHtml}
            ${planned ? `<span class="me-2">🗓️ ${esc(planned)}</span>` : ''}
            ${!t.completed && due ? `<span class="me-2">⏰ ${esc(due)}</span>` : ''}
            ${est ? `<span class="me-2">⏳ ${esc(est)}</span>` : ''}
            ${priority ? `<span class="badge priority-badge ms-2">Needs Attention</span>` : ''}
            ${dueToday ? `<span class="badge due-today-badge ms-2">Due Today</span>` : ''}
            ${overdue ? `<span class="badge overdue-badge ms-2">Overdue</span>` : ''}
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

function buildTaskActionButtons(taskId){
  return `
    <div class="d-flex justify-content-end gap-2 mt-3">
      <button class="btn btn-plain btn-sm" onclick="saveDetails(${taskId})">Save Task</button>
      <button class="btn btn-plain btn-sm text-danger" onclick="deleteTask(${taskId})">Delete Task</button>
    </div>
  `;
}


function buildDetailsPanel(t){
  const planned = t.planned_date || '';
  const due = t.due_date || '';
  const est = t.estimated_minutes || '';
  const repeat = t.repeat_rule || '';

  const folderId = t.folder ? String(t.folder) : '';
  const selectedSpaces = Array.isArray(t.spaces) ? t.spaces.map(x => String(x)) : [];
  const outstandingNextActionCount = Number(t.outstanding_next_action_count) || 0;
  const notesCount = Number(t.notes_count) || 0;
  const fileCount = Number(t.file_count) || 0;

  return `
    <div class="border-top pt-3">
      <div class="task-tabs-bar">
      <button class="btn btn-plain btn-sm tab-btn active" onclick="showTab(${t.id}, 'details')">Details</button>
      <button class="btn btn-plain btn-sm tab-btn" onclick="showTab(${t.id}, 'actions')">
        <span>Next Actions</span>
        <span id="actions-count-${t.id}" class="task-content-count${outstandingNextActionCount ? '' : ' d-none'}" aria-label="${outstandingNextActionCount} outstanding next actions">${outstandingNextActionCount || ''}</span>
      </button>
      <button class="btn btn-plain btn-sm tab-btn" onclick="showTab(${t.id}, 'notes')">
        <span>Notes</span>
        <span id="notes-count-${t.id}" class="task-content-count${notesCount ? '' : ' d-none'}" aria-label="${notesCount} saved notes">${notesCount || ''}</span>
      </button>
      <button class="btn btn-plain btn-sm tab-btn" onclick="showTab(${t.id}, 'files')">
        <span>Files</span>
        <span id="files-count-${t.id}" class="task-content-count${fileCount ? '' : ' d-none'}" aria-label="${fileCount} stored files">${fileCount || ''}</span>
      </button>
      </div>

      <div id="tab-${t.id}-details" class="tab-panel show">
      <div class="row g-2">

        <div class="col-12">
          <label class="form-label small">Task name</label>
          <input class="form-control form-control-sm" id="title-${t.id}" type="text" value="${esc(t.title || '')}">
        </div>

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
            <input class="form-control form-control-sm" id="due-${t.id}" type="date" value="${esc(due)}" ${repeat ? 'disabled' : ''}>
          </div>
          <div class="col-12 col-md-4">
            <label class="form-label small">Estimated time</label>
            ${buildEstimateSelectHtml(t.id, est)}
          </div>

          <div class="col-12 col-md-6">
            <label class="form-label small">Repeat</label>
            <select class="form-select form-select-sm" id="repeat-${t.id}" onchange="toggleDueDateForRepeat(${t.id})">
              <option value="" ${repeat === '' ? 'selected' : ''}>Does not repeat</option>
              <option value="EVERY_DAY" ${repeat === 'EVERY_DAY' ? 'selected' : ''}>Every day</option>
              <option value="EVERY_2_DAYS" ${repeat === 'EVERY_2_DAYS' ? 'selected' : ''}>Every 2 days</option>
              <option value="WEEKLY" ${repeat === 'WEEKLY' ? 'selected' : ''}>Every week</option>
              <option value="EVERY_2_WEEKS" ${repeat === 'EVERY_2_WEEKS' ? 'selected' : ''}>Every 2 weeks</option>
              <option value="MONTHLY" ${repeat === 'MONTHLY' ? 'selected' : ''}>Every month</option>
              <option value="EVERY_2_MONTHS" ${repeat === 'EVERY_2_MONTHS' ? 'selected' : ''}>Every 2 months</option>
            </select>
          </div>
        </div>

        ${buildTaskActionButtons(t.id)}


        <div id="save-msg-${t.id}" class="small text-success mt-2 d-none">Saved.</div>
        <div id="save-err-${t.id}" class="small text-danger mt-2 d-none"></div>
      </div>

      <div id="tab-${t.id}-actions" class="tab-panel">
        <div class="d-flex gap-2 mb-2">
          <input id="new-action-${t.id}" class="form-control form-control-sm" placeholder="Add a next action">
          <button class="btn btn-plain btn-sm" onclick="addAction(${t.id})">Add</button>
        </div>
        <ul id="actions-list-${t.id}" class="list-unstyled mb-0"></ul>
        ${buildTaskActionButtons(t.id)}
      </div>

      <div id="tab-${t.id}-notes" class="tab-panel">
        <div class="d-flex gap-2 mb-2">
          <textarea id="new-note-${t.id}" class="form-control form-control-sm" rows="2" placeholder="Add a note"></textarea>
          <button class="btn btn-plain btn-sm" onclick="addNote(${t.id})">Add</button>
        </div>
        <div id="notes-list-${t.id}"></div>
        ${buildTaskActionButtons(t.id)}
      </div>

      <div id="tab-${t.id}-files" class="tab-panel">
        <div id="files-panel-${t.id}" aria-live="polite">
          <div class="text-muted small">Loading files...</div>
        </div>
        ${buildTaskActionButtons(t.id)}
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
  const tabMap = ['details','actions','notes','files'];
  const idx = tabMap.indexOf(tab);
  if(idx >= 0 && buttons[idx]) buttons[idx].classList.add('active');

  if(tab === 'notes') loadNotes(taskId);
  if(tab === 'actions') loadActions(taskId);
  if(tab === 'files') loadFiles(taskId);
}
window.showTab = showTab;

async function openDetails(taskId){
  const el = document.getElementById('details-' + taskId);
  if(!el) return;
  el.classList.toggle('d-none');
  if(!el.classList.contains('d-none')){
    toggleDueDateForRepeat(taskId);  // <-- ADD THIS
    await loadNotes(taskId);
    await loadActions(taskId);
  }
}
window.openDetails = openDetails;

async function toggleComplete(taskId){
  const scrollY = window.scrollY;

  await apiSend(`${API.tasks}${taskId}/complete/`, 'POST', {});

  if(activeView === 'calendar'){
    await renderCalendarRange();
  } else {
    await renderListByFilter();
  }

  await refreshWorkspaceAchievements();

  window.scrollTo({
    top: scrollY,
    behavior: 'auto'
  });
}
window.toggleComplete = toggleComplete;

async function saveDetails(taskId){
  const title = (document.getElementById('title-' + taskId)?.value || '').trim();
  const planned = document.getElementById('planned-' + taskId)?.value || null;
  const repeat = document.getElementById('repeat-' + taskId)?.value || '';
  const dueInput = document.getElementById('due-' + taskId);
  const due = repeat ? null : (dueInput?.value || null);
  const est = document.getElementById('est-' + taskId)?.value || null;

  const folderVal = document.getElementById('folder-' + taskId)?.value || null;

  const spaceChecks = Array.from(document.querySelectorAll('.space-check-' + taskId));
  const validSpaceIds = new Set(
    (spacesCache || []).map(s => String(s.id))
  );

  const spaces = spaceChecks
    .filter(ch => ch.checked)
    .map(ch => ch.value)
    .filter(value => validSpaceIds.has(String(value)))
    .map(value => parseInt(value, 10))
    .filter(n => Number.isFinite(n));

    const payload = {
      title: title,
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
    console.log("SAVE DETAILS PAYLOAD", payload);
    await apiSend(`${API.tasks}${taskId}/`, 'PATCH', payload);
    await savePendingTaskTextItems(taskId);

    const summary = document.getElementById('spaces-summary-' + taskId);
    if(summary){
      summary.innerHTML = buildSpacesSummaryHtml(spaces.map(String));
    }

    if(msg){
      msg.classList.remove('d-none');
      setTimeout(() => msg.classList.add('d-none'), 1200);
    }

    if(activeView === 'calendar'){
      await renderCalendarRange();
    } else {
      await renderListByFilter();
    }

    await refreshWorkspaceAchievements();

  }catch(e){
    let message = 'Could not save task. Please check the task details.';

    try{
      const raw = String(e.message || '');
      const jsonStart = raw.indexOf('{');
      if(jsonStart >= 0){
        const parsed = JSON.parse(raw.slice(jsonStart));
        if(parsed.planned_date){
          message = parsed.planned_date[0];
        }else if(parsed.due_date){
          message = parsed.due_date[0];
        }else if(parsed.detail){
          message = parsed.detail;
        }
      }
    }catch(parseErr){}

    if(err){
      err.textContent = message;
      err.classList.remove('d-none');
    }else{
      alert(message);
    }
  }
}
window.saveDetails = saveDetails;

async function savePendingTaskTextItems(taskId){
  const actionInput = document.getElementById('new-action-' + taskId);
  const noteInput = document.getElementById('new-note-' + taskId);
  const actionTitle = (actionInput?.value || '').trim();
  const noteText = (noteInput?.value || '').trim();

  if(actionTitle){
    await apiSend(`${API.tasks}${taskId}/actions/`, 'POST', { title: actionTitle });
    if(actionInput) actionInput.value = '';
  }

  if(noteText){
    await apiSend(`${API.tasks}${taskId}/notes/`, 'POST', { text: noteText });
    if(noteInput) noteInput.value = '';
  }
}

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
function updateTaskContentCount(taskId, section, count){
  const badge = document.getElementById(`${section}-count-${taskId}`);
  if(!badge) return;

  const value = Math.max(0, Number(count) || 0);
  badge.textContent = value ? String(value) : '';
  badge.classList.toggle('d-none', value === 0);
  const labels = {
    actions: `${value} outstanding next actions`,
    notes: `${value} saved notes`,
    files: `${value} stored files`,
  };
  badge.setAttribute('aria-label', labels[section] || String(value));
}

function formatFileSize(bytes){
  const value = Number(bytes) || 0;
  if(value < 1024) return `${value} B`;
  if(value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

async function loadFiles(taskId){
  const panel = document.getElementById(`files-panel-${taskId}`);
  if(!panel) return;

  panel.innerHTML = '<div class="text-muted small">Loading files...</div>';
  try{
    const result = await apiGet(`${API.tasks}${taskId}/files/`);
    updateTaskContentCount(taskId, 'files', result.count);

    panel.innerHTML = `
      <form class="task-file-upload-form mb-3" onsubmit="event.preventDefault(); uploadTaskFile('${taskId}', this)">
        <label class="form-label small fw-semibold" for="task-file-${taskId}">Upload a file</label>
        <div class="d-flex gap-2 task-file-upload-row">
          <input
            id="task-file-${taskId}"
            name="file"
            type="file"
            class="form-control form-control-sm"
            accept=".pdf,.png,.jpg,.jpeg,.gif,.webp,.txt,.csv,.docx,.xlsx"
          >
          <button class="btn btn-plain btn-sm" type="submit">Upload</button>
        </div>
        <div class="task-file-error text-danger small mt-1" role="alert"></div>
      </form>
      <div class="task-files-list"></div>
    `;

    const list = panel.querySelector('.task-files-list');
    const files = result.files || [];
    if(!files.length){
      list.innerHTML = '<div class="text-muted small">No files yet.</div>';
      return;
    }

    files.forEach(file => {
      const row = document.createElement('div');
      row.className = 'task-file-row';
      row.innerHTML = `
        <div class="task-file-details">
          <div class="task-file-name" title="${esc(file.filename || '')}">${esc(file.filename || 'File')}</div>
          <div class="small text-muted">
            ${esc(formatFileSize(file.size))}
            ${file.uploaded_at ? ` · ${esc(fmtUIDateTimeFromISO(file.uploaded_at))}` : ''}
          </div>
        </div>
        <div class="task-file-actions">
          <a class="btn btn-plain btn-sm" href="${esc(file.download_url)}?inline=true" target="_blank" rel="noopener">Open</a>
          <a class="btn btn-plain btn-sm" href="${esc(file.download_url)}">Download</a>
          <button class="btn btn-plain btn-sm text-danger" type="button" onclick="deleteTaskFile('${taskId}', '${file.id}')">Delete</button>
        </div>
      `;
      list.appendChild(row);
    });
  }catch(error){
    panel.innerHTML = '<div class="text-danger small">Could not load files. Please try again.</div>';
  }
}

async function uploadTaskFile(taskId, form){
  if(form.dataset.uploading === 'true') return;
  const input = form.querySelector('input[type="file"]');
  const button = form.querySelector('button[type="submit"]');
  const error = form.querySelector('.task-file-error');
  if(!input?.files?.length) return;

  form.dataset.uploading = 'true';
  input.disabled = true;
  button.disabled = true;
  button.textContent = 'Uploading...';
  error.textContent = '';

  try{
    const data = new FormData();
    data.append('file', input.files[0]);
    await apiSend(`${API.tasks}${taskId}/files/`, 'POST', data, true);
    await loadFiles(taskId);
  }catch(uploadError){
    let message = 'Could not upload this file. Check its type and size, then try again.';
    const raw = String(uploadError?.message || '');
    const jsonStart = raw.indexOf('{');
    if(jsonStart >= 0){
      try{
        const details = JSON.parse(raw.slice(jsonStart));
        const fileError = Array.isArray(details.file) ? details.file[0] : details.file;
        if(fileError) message = String(fileError);
      }catch(parseError){}
    }
    error.textContent = message;
    input.disabled = false;
    button.disabled = false;
    button.textContent = 'Upload';
    form.dataset.uploading = 'false';
  }
}
window.uploadTaskFile = uploadTaskFile;

async function deleteTaskFile(taskId, fileId){
  if(!confirm('Delete this file permanently?')) return;
  await apiSend(`${API.tasks}${taskId}/files/${fileId}/`, 'DELETE', null);
  await loadFiles(taskId);
}
window.deleteTaskFile = deleteTaskFile;

async function loadNotes(taskId){
  const listEl = document.getElementById('notes-list-' + taskId);
  if(!listEl) return;
  listEl.innerHTML = '';

  const res = await apiGet(`${API.tasks}${taskId}/notes/`);
  const notes = res.results || res || [];
  updateTaskContentCount(taskId, 'notes', notes.length);

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
          <div id="note-text-display-${n.id}" class="small note-text-display">${esc(n.text)}</div>
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
  await refreshWorkspaceAchievements();
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
  updateTaskContentCount(
    taskId,
    'actions',
    items.filter(item => !(item.completed ?? item.done)).length
  );

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
  await refreshWorkspaceAchievements();
}
window.addAction = addAction;


async function deleteAction(taskId, actionId){
  await apiSend(`${API.tasks}${taskId}/actions/${actionId}/`, 'DELETE', null);
  await loadActions(taskId);
}
window.deleteAction = deleteAction;

/* Folder and space edit/delete */

function sidebarPinError(error, fallback){
  const message = String(error?.message || '');
  const match = message.match(/"is_pinned":\s*\["([^"]+)"/);
  alert(match ? match[1] : fallback);
}

async function toggleFolderPin(folderId){
  const folder = (foldersCache || []).find(f => String(f.id) === String(folderId));
  if(!folder) return;

  try{
    await apiSend(`${API.folders}${folderId}/`, 'PATCH', {
      is_pinned: !folder.is_pinned
    });
    await renderSidebar();
  }catch(e){
    sidebarPinError(e, 'You can pin up to 3 folders.');
  }
}
window.toggleFolderPin = toggleFolderPin;

async function deleteFolder(folderId){
  const folder = (foldersCache || []).find(f => String(f.id) === String(folderId));
  const folderName = folder ? folder.name : 'this folder';

  let taskCount = 0;

  try{
    const r = await apiGet(`${API.tasks}?folder=${folderId}&page_size=1`);
    taskCount = typeof r.count === 'number' ? r.count : (r.results || r || []).length;
  }catch(e){}

  const msg =
    `WARNING: You are about to delete the folder "${folderName}".\n\n` +
    `This folder currently has ${taskCount} task(s).\n\n` +
    `If you continue, Finy will permanently delete:\n` +
    `• the folder\n` +
    `• all tasks inside the folder\n` +
    `• their notes, next actions and attachments\n\n` +
    `This cannot be undone.\n\n` +
    `Click OK to permanently delete, or Cancel to keep it.`;

  if(!confirm(msg)) return;

  await apiSend(`${API.folders}${folderId}/`, 'DELETE', null);
  await renderSidebar();
  await showInbox();
}
window.deleteFolder = deleteFolder;

function startEditFolder(folderId){
  const folder = (foldersCache || []).find(f => String(f.id) === String(folderId));
  if(!folder) return;

  const li = document.querySelector(`#folderList li[data-id="${folderId}"]`);
  if(!li) return;

  li.innerHTML = `
    <div class="w-100">
      <input id="edit-folder-name-${folderId}" class="form-control form-control-sm mb-2" value="${esc(folder.name || '')}">
      <div class="d-flex gap-2 justify-content-end">
        <button class="btn btn-plain btn-sm" onclick="cancelEditFolder()">Cancel</button>
        <button class="btn btn-plain btn-sm" onclick="saveFolder('${folderId}')">Save</button>
      </div>
      <div id="edit-folder-error-${folderId}" class="text-danger small mt-1 d-none"></div>
    </div>
  `;

  document.getElementById(`edit-folder-name-${folderId}`)?.focus();
}
window.startEditFolder = startEditFolder;

async function saveFolder(folderId){
  const name = (document.getElementById(`edit-folder-name-${folderId}`)?.value || '').trim();
  const err = document.getElementById(`edit-folder-error-${folderId}`);

  if(!name){
    if(err){
      err.textContent = 'Folder name is required.';
      err.classList.remove('d-none');
    }
    return;
  }

  try{
    await apiSend(`${API.folders}${folderId}/`, 'PATCH', { name });
    await renderSidebar();
  }catch(e){
    if(err){
      err.textContent = 'Could not update folder. The name may already exist.';
      err.classList.remove('d-none');
    }
  }
}
window.saveFolder = saveFolder;

async function cancelEditFolder(){
  await renderSidebar();
}
window.cancelEditFolder = cancelEditFolder;

async function toggleSpacePin(spaceId){
  const space = (spacesCache || []).find(s => String(s.id) === String(spaceId));
  if(!space) return;

  try{
    await apiSend(`${API.spaces}${spaceId}/`, 'PATCH', {
      is_pinned: !space.is_pinned
    });
    await renderSidebar();
  }catch(e){
    sidebarPinError(e, 'You can pin up to 3 spaces.');
  }
}
window.toggleSpacePin = toggleSpacePin;

async function deleteSpace(spaceId){
  const space = (spacesCache || []).find(s => String(s.id) === String(spaceId));
  const spaceName = space ? space.name : 'this space';

  if(String(spaceName || '').toLowerCase() === 'waiting_for'){
    alert('waiting_for is a special space and cannot be deleted.');
    return;
  }

  let taskCount = 0;

  try{
    const r = await apiGet(`${API.tasks}?spaces=${spaceId}&page_size=1`);
    taskCount = typeof r.count === 'number'
      ? r.count
      : (r.results || r || []).length;
  }catch(e){}

  const msg =
    `WARNING: You are about to delete the space "${spaceName}".\n\n` +
    `This space is currently linked to ${taskCount} task(s).\n\n` +
    `Deleting the space will:\n` +
    `• permanently remove the space\n` +
    `• remove the space from all linked tasks\n\n` +
    `The tasks themselves will NOT be deleted.\n\n` +
    `Click OK to continue, or Cancel to keep it.`;

  if(!confirm(msg)) return;

  await apiSend(`${API.spaces}${spaceId}/`, 'DELETE', null);

  await renderSidebar();
  await renderListByFilter();
}
window.deleteSpace = deleteSpace;

function startEditSpace(spaceId){
  const space = (spacesCache || []).find(s => String(s.id) === String(spaceId));
  if(!space) return;

  const li = document.querySelector(`#spaceList li[data-id="${spaceId}"]`);
  if(!li) return;

  const categoryOptions = (categoriesCache || [])
    .map(c => {
      const selected = String(c.id) === String(space.category) ? 'selected' : '';
      return `<option value="${c.id}" ${selected}>${esc(c.name)}</option>`;
    })
    .join('');

  li.innerHTML = `
    <div class="w-100">
      <input id="edit-space-name-${spaceId}" class="form-control form-control-sm mb-2" value="${esc(space.name || '')}">

      <select id="edit-space-category-${spaceId}" class="form-select form-select-sm mb-2">
        ${categoryOptions}
      </select>

      <div class="d-flex gap-2 justify-content-end">
        <button class="btn btn-plain btn-sm" onclick="cancelEditSpace()">Cancel</button>
        <button class="btn btn-plain btn-sm" onclick="saveSpace('${spaceId}')">Save</button>
      </div>

      <div id="edit-space-error-${spaceId}" class="text-danger small mt-1 d-none"></div>
    </div>
  `;

  document.getElementById(`edit-space-name-${spaceId}`)?.focus();
}
window.startEditSpace = startEditSpace;

async function saveSpace(spaceId){
  const name = (document.getElementById(`edit-space-name-${spaceId}`)?.value || '').trim();
  const category = document.getElementById(`edit-space-category-${spaceId}`)?.value || '';

  const err = document.getElementById(`edit-space-error-${spaceId}`);

  if(!name || !category){
    if(err){
      err.textContent = 'Name and category are required.';
      err.classList.remove('d-none');
    }
    return;
  }

  try{
    await apiSend(`${API.spaces}${spaceId}/`, 'PATCH', {
      name,
      category: parseInt(category, 10)
    });

    await renderSidebar();
    await renderListByFilter();
  }catch(e){
    if(err){
      err.textContent = 'Could not update space.';
      err.classList.remove('d-none');
    }
  }
}
window.saveSpace = saveSpace;

async function cancelEditSpace(){
  await renderSidebar();
}
window.cancelEditSpace = cancelEditSpace;

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
