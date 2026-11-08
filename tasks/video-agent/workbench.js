/* The same workbench runs standalone at / or mounted in AppDNA at /video/. */
const $ = id => document.getElementById(id);
const BASE = document.currentScript.dataset.base ?? location.pathname.replace(/\/$/, '');
const resource = path => BASE + path;
const ACTIVE = new Set(['queued', 'fetching_video', 'separating_media', 'learning',
  'checking_artifact_targets', 'running', 'starting_blender', 'saving_artifact','paused','resuming']);
let current = null, loaded = null, locked = true, jobsVersion = '', refreshing = false;

async function api(path, options = {}) {
  const response = await fetch(resource(path), options);
  let data;
  try { data = await response.json(); }
  catch { throw Error(`Request failed (${response.status}). Check that the AppDNA API is running.`); }
  if (!response.ok) throw Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data));
  return data;
}
function msg(text) { $('message').textContent = text; }

async function list() {
  const jobs = await api('/api/tutorials');
  const version = JSON.stringify(jobs);
  if (version === jobsVersion) return jobs;
  jobsVersion = version;
  $('jobs').replaceChildren();
  for (const job of jobs) {
    const button = document.createElement('button');
    button.className = 'job'; button.dataset.id = job.id;
    button.textContent = `${job.title || 'Blender tutorial'} · ${job.status.replaceAll('_', ' ')}`;
    button.onclick = () => select(job.id).catch(error => msg(error.message));
    $('jobs').append(button);
  }
  return jobs;
}

async function select(id) {
  current = id; loaded = null;
  history.replaceState(null, '', `#${id}`);
  $('approve').checked = false;
  for (const id of ['run','resume','project','reuse','stop','topstop']) $(id).disabled = true;
  $('sourceagent').classList.add('hidden');
  $('projectlink').classList.add('hidden');
  $('screenshot').classList.add('hidden');
  $('steps').replaceChildren(); $('evidence').textContent = '';
  $('video').removeAttribute('src');
  await refresh();
}

function makeSteps(plan) {
  $('steps').replaceChildren();
  for (const [index, step] of plan.steps.entries()) {
    const button = document.createElement('button'); button.className = 'step';
    const strong = document.createElement('strong'); strong.textContent = `${index + 1}. ${step.instruction}`;
    const span = document.createElement('span');
    span.textContent = `${step.start.toFixed(1)}s → ${step.end.toFixed(1)}s · ${step.expected}`;
    button.append(strong, span);
    if (step.uncertainty && step.uncertainty.toLowerCase() !== 'none') {
      const em = document.createElement('em'); em.textContent = `Uncertainty: ${step.uncertainty}`; button.append(em);
    }
    button.onclick = () => { $('video').currentTime = step.start; };
    $('steps').append(button);
  }
}

function showSourceAgent(job) {
  $('sourceagent').classList.toggle('hidden', !job.agent);
  if (!job.agent) return;
  $('learningstatus').textContent = `${(job.knowledge?.status || job.agent.status).replaceAll('_', ' ')} · ${job.agent.model} · ${(job.agent.events || []).length} decisions`;
  $('agenttrace').replaceChildren();
  for (const event of job.agent.events || []) {
    const li = document.createElement('li');
    let outcome = event.result?.error || '';
    if (event.result?.source_checks) outcome = event.result.accepted ? 'Source checks passed' : event.result.source_checks.flatMap(check => check.issues).join(' ');
    if (event.result?.evidence) outcome = event.result.evidence.map(frame => `${frame.id} @ ${frame.timestamp.toFixed(2)}s`).join(', ');
    li.textContent = `${String(event.action || 'invalid decision').replaceAll('_', ' ')} — ${event.reason || ''}${outcome ? ' → ' + outcome : ''}`;
    $('agenttrace').append(li);
  }
  $('knowledgeDownload').classList.toggle('hidden', !job.knowledge);
  $('knowledgeDownload').href = resource('/api/video-sources/' + current);
}

async function refresh() {
  if (refreshing) return;
  refreshing = true;
  const selected = current;
  try {
    const [desktop, job] = await Promise.all([
      api('/api/desktop').catch(error => ({locked: true, available: false, reason: error.message})),
      selected ? api('/api/tutorials/' + selected) : null,
    ]);
    locked = desktop.locked || desktop.available === false;
    $('desktop').textContent = desktop.available === false ? 'Desktop unavailable' : locked ? 'Mac locked · Execution blocked' : 'Desktop unlocked';
    $('desktop').title = desktop.reason || '';
    if (!job || current !== selected) return;
    $('empty').classList.add('hidden'); $('detail').classList.remove('hidden');
    $('status').textContent = job.status.replaceAll('_', ' ');
    $('error').textContent = job.error || '';
    $('title').textContent = job.plan?.title || job.title;
    $('goal').textContent = job.plan?.objective || job.objective;
    showSourceAgent(job);
    $('project').disabled = job.knowledge?.status !== 'source_checked';
    $('reuse').disabled = job.knowledge?.status !== 'source_checked';
    $('targetpanel').classList.toggle('hidden', !job.artifact_targets);
    if (job.artifact_targets) $('targets').textContent = JSON.stringify({scope: job.artifact_targets.scope,
      expected: job.artifact_targets.values, evidence_ids: job.artifact_targets.evidence_ids,
      source_check: job.artifact_targets.source_check}, null, 2);
    if (job.source_file && !$('video').getAttribute('src')) $('video').src = resource(`/assets/${current}/${job.source_file}`);
    if (job.plan && loaded !== current) {
      loaded = current; makeSteps(job.plan);
      $('evidence').textContent = JSON.stringify({prerequisites: job.plan.prerequisites,
        limitations: job.plan.limitations, transcript_origin: job.transcript_origin || 'gladia',
        transcript_segments: job.transcript?.length, sampled_frames: job.media?.frames?.length,
        inspected_frames: job.knowledge?.evidence?.length,
        video_source: job.knowledge, reused_from: job.reused_from, reuse: job.reuse}, null, 2);
    }
    $('runhint').textContent = desktop.reason || (locked ? 'Mac locked — unlock the Mac to enable execution.' : '');
    $('topstop').disabled = !ACTIVE.has(job.status); $('stop').disabled = !ACTIVE.has(job.status);
    $('run').disabled = locked || !job.plan || (job.knowledge && job.knowledge.status !== 'source_checked') ||
      !$('approve').checked || !!job.run || ACTIVE.has(job.status);
    $('resume').classList.toggle('hidden',job.status!=='paused');
    $('resume').disabled = job.status!=='paused' || locked || !$('approve').checked;
    $('artifact').classList.toggle('hidden', !job.verification);
    if (job.verification) {
      $('artifactstatus').textContent = 'Independent artifact check: ' + job.verification.verification;
      $('checks').textContent = JSON.stringify(job.verification.checks ? {scope: job.verification.scope,
        checks: job.verification.checks, expected: job.verification.expected, measured: job.verification.measured,
        read_only_hash_unchanged: job.verification.read_only_hash_unchanged} : {reason: job.verification.reason}, null, 2);
      $('blendlink').hidden = !job.verification.artifact;
      $('blendlink').href = resource(`/assets/${current}/run/replica.blend`);
    }
    $('execution').classList.toggle('hidden', !job.run);
    if (job.run) {
      $('runstatus').textContent = `${job.run.status} · ${job.run.verification}`;
      const events = job.run.events || [];
      $('receipt').textContent = events.map(event => `${event.step} · ${event.action.action} · ${event.action.reason || ''}`).join('\n');
      const last = [...events].reverse().find(event => event.after || event.before);
      if (last) {
        const src = resource(`/assets/${current}/run/${last.after || last.before}`);
        if ($('screenshot').getAttribute('src') !== src) $('screenshot').src = src;
        $('screenshot').classList.remove('hidden');
      }
    }
  } finally { refreshing = false; }
}

$('sample').onclick = () => {
  $('url').value = 'https://www.youtube.com/watch?v=l12k19-imCY';
  $('file').value = '';
  msg('Blender example selected. Click Learn from video to start a fresh source-learning run.');
};
$('approve').onchange = () => refresh().catch(error => msg(error.message));
$('form').onsubmit = async event => {
  event.preventDefault(); $('learn').disabled = true;
  try {
    const video = $('file').files[0], transcript = $('transcript').files[0];
    if (video && video.size > 100 * 1024 * 1024) throw Error('Video exceeds 100 MB');
    if (transcript && transcript.size > 2 * 1024 * 1024) throw Error('Transcript exceeds 2 MB');
    const data = new FormData(); data.set('url', $('url').value); data.set('objective', $('objective').value);
    if (video) data.set('video', video);
    if (transcript) data.set('transcript', transcript);
    const job = await api('/api/tutorials', {method: 'POST', body: data});
    msg('Learning started. The agent reads narration, revisits frames and checks proposed steps against the source.');
    await list(); await select(job.id);
  } catch (error) { msg(error.message); }
  finally { $('learn').disabled = false; }
};
$('project').onclick = async () => {
  $('project').disabled = true;
  try {
    const project = await api(`/api/tutorials/${current}/project`, {method: 'POST'});
    $('projectlink').href = project.url; $('projectlink').classList.remove('hidden');
  } catch (error) { $('error').textContent = error.message; }
  finally { $('project').disabled = false; }
};
$('run').onclick = async () => {
  if (!$('approve').checked || locked) return;
  $('run').disabled = true;
  try {
    await api(`/api/tutorials/${current}/run`, {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({confirm_scratch: true, reviewed: true})});
    await refresh();
  } catch (error) { $('error').textContent = error.message; }
};
$('reuse').onclick = async () => {
  $('reuse').disabled = true;
  try {
    const job = await api(`/api/video-sources/${current}/reuse`, {method: 'POST'});
    await list(); await select(job.id);
    $('error').textContent = 'Checked knowledge reused. Review the steps and approve a new isolated scratch run.';
  } catch (error) { $('error').textContent = error.message; }
  finally { $('reuse').disabled = false; }
};
$('resume').onclick = async () => {
  if (!$('approve').checked || locked) return;
  $('resume').disabled = true;
  try {
    await api(`/api/tutorials/${current}/resume`, {method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({reviewed:true,confirm_scratch:true})});
    await refresh();
  } catch (error) { $('error').textContent = error.message; }
};
$('topstop').onclick = () => $('stop').click();
$('stop').onclick = async () => {
  try {
    await api(`/api/tutorials/${current}/stop`, {method: 'POST'});
    $('error').textContent = 'Stop requested. No further input will be issued after the current input operation.';
  } catch (error) { $('error').textContent = error.message; }
};

(async () => {
  try {
    const [jobs, runtime] = await Promise.all([list(), api('/api/runtime')]);
    const issues = [];
    if (!runtime.providers.hcompany) issues.push('Configure HCOMPANY_API_KEY to learn from video.');
    if (!runtime.providers.gladia) issues.push('No Gladia key: use YouTube captions or supply a transcript.');
    for (const [name, available] of Object.entries(runtime.tools)) if (!available) issues.push(`${name} is not installed.`);
    $('runtime').textContent = issues.join(' ');
    const requested = location.hash.slice(1);
    if (jobs.length) await select(jobs.find(job => job.id === requested)?.id || jobs[0].id);
    else await refresh();
  } catch (error) { msg(error.message); }
})();
setInterval(() => {
  if (document.hidden) return;
  Promise.all([refresh(), list()]).catch(error => msg(error.message));
}, 2500);
