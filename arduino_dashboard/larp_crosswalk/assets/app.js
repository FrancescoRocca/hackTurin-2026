'use strict';
const canvas = document.querySelector('#preview');
const ctx = canvas.getContext('2d', {alpha:false});
const message = document.querySelector('#message');
const status = document.querySelector('#status');
const pause = document.querySelector('#pause');
let paused = false;
let sequence = 0;
let timer;
let busy = false;
let pixels = null;
let resultSequence = null;
let hadResult = false;
let statsTimer;
let statsBusy = false;
let clearingDatabase = false;
const numberFormat = new Intl.NumberFormat();
const classNames = {person:'Person',car:'Car',bicycle:'Bicycle',motorcycle:'Motorbike'};
function localTime(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
}
function countText(value) { return Number.isSafeInteger(value) && value >= 0 ? numberFormat.format(value) : '—'; }
function showStats(data) {
  for (const key of Object.keys(classNames)) {
    document.querySelector(`#total-${key}`).textContent = countText(data.totals[key]);
    document.querySelector(`#pending-${key}`).textContent = countText(data.counts_since_last_sync[key]);
  }
  const queued = `${countText(data.pending_batches)} hourly ${data.pending_batches === 1 ? 'batch' : 'batches'} queued`;
  const syncState = document.querySelector('#sync-state');
  syncState.textContent = `${!data.server_configured ? 'Server not configured' : data.last_sync_error ? 'Upload delayed · retrying' : 'Hourly uploads enabled'} · ${queued}`;
  syncState.dataset.state = data.server_configured && data.last_sync_error ? 'error' : 'ready';
  document.querySelector('#last-sync').textContent = data.last_synced_timestamp
    ? `Synced through ${new Date(data.last_synced_timestamp).toLocaleString()}` : 'No uploads completed yet.';
  const list = document.querySelector('#recent-sightings');
  list.replaceChildren();
  for (const item of data.recent_sightings || []) {
    const row = document.createElement('tr');
    for (const value of [classNames[item.class] || item.class, localTime(item.timestamp), `${Number(item.confidence).toFixed(1)}%`]) {
      const cell = document.createElement('td'); cell.textContent = value; row.append(cell);
    }
    list.append(row);
  }
  if (!list.children.length) {
    const row = document.createElement('tr'); const cell = document.createElement('td');
    cell.colSpan = 3; cell.className = 'empty'; cell.textContent = 'No confirmed sightings yet.';
    row.append(cell); list.append(row);
  }
  const updated = document.querySelector('#stats-updated');
  updated.dateTime = new Date().toISOString(); updated.textContent = `Updated ${localTime(updated.dateTime)}`;
}
async function refreshStats() {
  if (statsBusy || document.hidden || clearingDatabase) return;
  statsBusy = true;
  const state = document.querySelector('#stats-state');
  try {
    const response = await fetch('/api/stats', {cache:'no-store',signal:AbortSignal.timeout(5000)});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (clearingDatabase) return;
    showStats(data);
    state.textContent = 'Statistics connected'; state.dataset.state = 'ready';
  } catch (error) {
    state.textContent = 'Statistics unavailable · retrying'; state.dataset.state = 'error';
  } finally {
    statsBusy = false; clearTimeout(statsTimer);
    if (!document.hidden) statsTimer = setTimeout(refreshStats, 5000);
  }
}
function setStatus(text, state) { status.textContent = text; status.dataset.state = state; }
function showResults(data) {
  document.querySelector('#latency').textContent = data.inference_ms === null ? '—' : `${data.inference_ms} ms`;
  document.querySelector('#age').textContent = data.age_sec === null ? '—' : `${Number(data.age_sec).toFixed(1)} s`;
  document.querySelector('#detection-age').textContent = data.detection_age_ms === null ? '—' : `${(data.detection_age_ms / 1000).toFixed(1)} s`;
  document.querySelector('#rates').textContent = `${data.capture_fps} fps camera · ${data.detection_fps} detections/s`;
  if (resultSequence === data.detection_sequence && hadResult) return;
  hadResult = true; resultSequence = data.detection_sequence;
  const detections = data.detections || [];
  document.querySelector('#count').textContent = detections.length;
  const list = document.querySelector('#detections');
  list.replaceChildren();
  for (const item of detections) {
    const row = document.createElement('li');
    const label = document.createElement('strong'); label.textContent = item.class_name;
    const confidence = document.createElement('span'); confidence.textContent = `${Number(item.confidence).toFixed(1)}%`;
    row.append(label, confidence); list.append(row);
  }
  if (!detections.length) {
    const row = document.createElement('li'); row.className = 'empty';
    row.textContent = resultSequence === null ? 'Waiting for the first detection result.' : 'No objects detected in the latest result.';
    list.append(row);
  }
}
function draw(data) {
  if (!pixels) return;
  ctx.putImageData(pixels, 0, 0);
  // Hide old boxes after an interruption rather than leaving them stuck onscreen.
  if (data.status !== 'live' || data.detection_age_ms > 1500) return;
  ctx.lineWidth = 2;
  ctx.font = '14px system-ui, sans-serif';
  for (const detection of data.detections || []) {
    const bounds = detection.bounding_box_xyxy;
    if (!Array.isArray(bounds) || bounds.length !== 4 || !bounds.every(Number.isFinite)) continue;
    const [x1,y1,x2,y2] = bounds;
    ctx.strokeStyle = '#00ffba';
    ctx.strokeRect(x1, y1, x2-x1, y2-y1);
    const label = `${detection.class_name} ${Number(detection.confidence).toFixed(0)}%`;
    const width = Math.min(ctx.measureText(label).width + 12, canvas.width);
    const x = Math.max(0, Math.min(x1, canvas.width-width));
    const y = Math.max(0, Math.min(y1-24, canvas.height-24));
    ctx.fillStyle = '#003b32'; ctx.fillRect(x,y,width,24);
    ctx.fillStyle = '#ffffff'; ctx.fillText(label,x+6,y+17,width-12);
  }
}
async function refresh() {
  if (paused || busy || document.hidden) return;
  busy = true;
  const started = performance.now();
  try {
    const response = await fetch(`/api/frame?since=${sequence}`, {cache:'no-store', signal:AbortSignal.timeout(5000)});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = JSON.parse(response.headers.get('X-Frame-Meta'));
    if (!data) throw new Error('Missing frame metadata');
    if (response.status !== 204) {
      const raw = new Uint8Array(await response.arrayBuffer());
      if (paused) return;
      if (raw.length !== data.width * data.height * 3) throw new Error('Incomplete RGB frame');
      if (!pixels || canvas.width !== data.width || canvas.height !== data.height) {
        canvas.width = data.width; canvas.height = data.height;
        pixels = ctx.createImageData(data.width, data.height);
        for (let i=3; i<pixels.data.length; i+=4) pixels.data[i]=255;
      }
      for (let src=0,dst=0; src<raw.length; src+=3,dst+=4) {
        pixels.data[dst]=raw[src]; pixels.data[dst+1]=raw[src+1]; pixels.data[dst+2]=raw[src+2];
      }
      sequence = data.sequence;
      canvas.dataset.sequence = sequence;
      canvas.hidden = false; message.hidden = true;
    }
    if (paused) return;
    showResults(data); draw(data);
    document.querySelector('#camera').textContent = `${data.source.replace('csi:', '')} · ${data.width} × ${data.height}`;
    const states = {live:'Live', waiting:'Waiting for camera', stale:'Camera delayed · retrying', error:'Camera or model error'};
    setStatus(states[data.status] || 'Waiting for camera', data.status);
    if (data.status === 'error') {
      message.textContent = 'Camera or detection stopped. Check the prova app logs and restart the app.';
      message.hidden = false;
    }
  } catch (error) {
    if (!paused) {
      setStatus('Disconnected · retrying', 'error');
      if (canvas.hidden) message.textContent = 'Cannot reach the camera. Check that prova is running. Retrying automatically…';
    }
  } finally {
    busy = false;
    clearTimeout(timer);
    if (!paused && !document.hidden) timer = setTimeout(refresh, Math.max(0,100-(performance.now()-started)));
  }
}
pause.addEventListener('click', () => {
  paused = !paused;
  pause.textContent = paused ? 'Resume preview' : 'Pause preview';
  clearTimeout(timer);
  if (paused) setStatus('Preview paused', 'paused'); else refresh();
});
document.addEventListener('visibilitychange', () => {
  clearTimeout(timer);
  clearTimeout(statsTimer);
  if (!document.hidden && !paused) refresh();
  if (!document.hidden) refreshStats();
});
refresh();
refreshStats();

const clearDatabase = document.querySelector('#clear-database');
clearDatabase.addEventListener('click', async () => {
  if (!window.confirm('Permanently delete all sightings and queued uploads on this board? Unsynced detections will be lost. Data already on the server stays unchanged. The camera will continue logging new sightings.')) return;
  clearingDatabase = true;
  clearDatabase.disabled = true;
  clearDatabase.textContent = 'Clearing…';
  const result = document.querySelector('#clear-result');
  result.textContent = 'Clearing the board database…';
  result.dataset.state = 'ready';
  try {
    const response = await fetch('/api/stats/clear-local', {
      method:'POST', headers:{'X-Confirm-Local-Reset':'delete-board-data'},
      signal:AbortSignal.timeout(30000), cache:'no-store'
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    showStats(await response.json());
    result.textContent = 'Board history cleared. New sightings will continue to be recorded.';
  } catch (error) {
    result.textContent = 'Could not confirm deletion. Refresh statistics before trying again.';
    result.dataset.state = 'error';
  } finally {
    clearingDatabase = false;
    clearDatabase.disabled = false;
    clearDatabase.textContent = 'Clear board database';
    refreshStats();
  }
});
