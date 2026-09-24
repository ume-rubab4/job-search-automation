import { useEffect, useMemo, useState } from 'react'

const VISA = {
  stated_yes: ['Sponsorship stated', 'teal'], known_sponsor: ['Known sponsor', 'teal'],
  not_mentioned: ['Visa not mentioned', 'amber'], stated_no: ['No sponsorship', 'rose'],
}
const STATUS = {
  emailed: 'Needs your decision', shortlisted: 'Shortlisted', approved: 'Approved, applying next run',
  applied: 'Applied', package_ready: 'Ready for you to submit', skipped: 'Skipped',
  apply_failed: 'Apply failed', rejected: 'Not a match', found: 'Found',
}
const api = (p, o) => fetch(`/api${p}`, o).then(async r => { if (!r.ok) throw new Error((await r.json()).detail || r.statusText); return r.json() })

const ringColor = s => (s >= 80 ? 'var(--teal)' : s >= 65 ? 'var(--blue)' : 'var(--amber)')
const greet = () => { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening' }

export default function App() {
  const [ov, setOv] = useState(null)
  const [jobs, setJobs] = useState([])
  const [tab, setTab] = useState('decide')
  const [sel, setSel] = useState(null)
  const [toast, setToast] = useState('')

  const load = async () => {
    const [o, j] = await Promise.all([api('/overview'), api('/jobs')])
    setOv(o); setJobs(j)
  }
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t) }, [])
  const say = m => { setToast(m); setTimeout(() => setToast(''), 3500) }

  const byFit = (a, b) => (b.fit_score || 0) - (a.fit_score || 0)
  const pending = jobs.filter(j => j.status === 'emailed').sort(byFit)
  const queued = jobs.filter(j => ['approved', 'package_ready', 'apply_failed'].includes(j.status)).sort(byFit)
  const applied = jobs.filter(j => j.status === 'applied').sort((a, b) => (b.applied_at || '').localeCompare(a.applied_at || ''))
  const top = jobs.filter(j => j.fit_score != null).sort(byFit).slice(0, 100)
  const counts = ov?.counts || {}

  if (!ov) return <div className="main"><p style={{ color: 'var(--muted)' }}>Connecting to your agent…</p></div>
  const first = ov.profile.name.split(' ')[0]
  const initials = ov.profile.name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase()

  const run = async mode => {
    const r = await api(`/run/${mode}`, { method: 'POST' })
    say(r.ok ? (mode === 'discover' ? 'Searching for new jobs. Takes 10–20 minutes.' : 'Applying to approved jobs. Results are emailed.') : 'Already running.')
    load()
  }

  return (
    <div className="app">
      <aside className="rail">
        <div className="who"><div className="avatar">{initials}</div><div><b>{first}</b><span>{ov.profile.headline.split('|')[0].trim()}</span></div></div>
        <Nav id="decide" tab={tab} setTab={setTab} n={counts.emailed || 0}>Needs your decision</Nav>
        <Nav id="top" tab={tab} setTab={setTab} n={top.length}>Top matches</Nav>
        <Nav id="pending" tab={tab} setTab={setTab} n={queued.length}>Pending</Nav>
        <Nav id="applied" tab={tab} setTab={setTab} n={applied.length}>Applied</Nav>
        <Nav id="all" tab={tab} setTab={setTab} n={ov.total}>All jobs</Nav>
        <Nav id="paste" tab={tab} setTab={setTab}>Paste a hiring post</Nav>
        <Nav id="profile" tab={tab} setTab={setTab}>My CV & profile</Nav>
        <div className="grow" />
        <div className="runbox">
          <button className="btn primary" onClick={() => run('discover')} disabled={ov.running.discover}>
            {ov.running.discover ? <><i className="spin" /> Searching…</> : 'Find new jobs now'}</button>
          <button className="btn" onClick={() => run('approvals')} disabled={ov.running.approvals}>
            {ov.running.approvals ? <><i className="spin" /> Applying…</> : 'Apply to approved jobs'}</button>
        </div>
      </aside>

      <main className="main">
        {tab === 'decide' && <Decide pending={pending} ov={ov} first={first} onOpen={setSel} go={setTab} />}
        {tab === 'top' && <TopMatches jobs={top} onOpen={setSel} />}
        {tab === 'pending' && <Pending jobs={queued} onOpen={setSel} running={ov.running.approvals} />}
        {tab === 'applied' && <Applied jobs={applied} onOpen={setSel} />}
        {tab === 'all' && <AllJobs jobs={jobs} onOpen={setSel} />}
        {tab === 'paste' && <Paste onAdded={j => { load(); setSel(j.id); say('Added. CV and email are ready to review.') }} />}
        {tab === 'profile' && <Profile profile={ov.profile} onSaved={() => { load(); say('Profile updated. Next run uses the new CV.') }} />}
      </main>

      {sel && jobs.find(j => j.id === sel) && <Drawer job={jobs.find(j => j.id === sel)} onClose={() => setSel(null)} refresh={load} say={say} />}
      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}

function Nav({ id, tab, setTab, n, children }) {
  return <button className={`nav ${tab === id ? 'on' : ''}`} onClick={() => setTab(id)}><span>{children}</span>{n !== undefined && <span className="n">{n}</span>}</button>
}

function Tags({ j }) {
  const [vt, vc] = VISA[j.visa_status] || ['Visa unknown', 'grey']
  const auto = j.platform && j.platform !== 'other'
  const method = j.contact_email ? ['Email application', 'violet'] : auto ? ['Auto-apply', 'blue'] : ['You submit', 'grey']
  return <div className="tags">
    <span className={`tag ${vc}`}>{vt}</span>
    <span className="tag grey">{j.company_size || 'unknown'} company</span>
    <span className={`tag ${method[1]}`}>{method[0]}</span>
    <span className="tag grey">{j.source}</span>
  </div>
}

function Ring({ s }) {
  const v = s || 0
  return <div className="ring" style={{ '--p': v, '--c': ringColor(v) }}><span>{v}</span></div>
}

function JobRow({ j, onOpen, sub }) {
  return <button className="job" onClick={() => onOpen(j.id)}>
    <Ring s={j.fit_score} />
    <div><div className="t">{j.title}</div><div className="m">{j.company} · {j.city ? `${j.city}, ` : ''}{j.country}{j.remote ? ' · Remote' : ''}</div><Tags j={j} /></div>
    <div className="st">{STATUS[j.status] || j.status}{sub && <div style={{ color: 'var(--muted)', fontSize: 12 }}>{sub}</div>}</div>
  </button>
}

function Decide({ pending, ov, first, onOpen, go }) {
  const c = ov.counts
  const visaTotal = Object.values(ov.visa).reduce((a, b) => a + b, 0) || 1
  const maxC = ov.by_country[0]?.[1] || 1
  const order = ['stated_yes', 'known_sponsor', 'not_mentioned', 'stated_no']
  const col = { stated_yes: 'var(--teal)', known_sponsor: '#5EE0CE', not_mentioned: 'var(--amber)', stated_no: 'var(--rose)' }
  return <>
    <div className="head">
      <h1>{pending.length ? `${pending.length} job${pending.length === 1 ? '' : 's'} need${pending.length === 1 ? 's' : ''} your decision` : `${greet()}, ${first}`}</h1>
      <p>{pending.length ? 'Each one matched your profile and has a tailored CV ready. Open a job to apply now, approve it for the next batch, or skip it.'
        : 'Nothing is waiting. The agent searches every morning and lists new matches here.'}</p>
    </div>
    <div className="stats">
      <Stat c="var(--blue)" v={c.emailed || 0} l="Waiting for you" onClick={() => go('decide')} />
      <Stat c="var(--teal)" v={c.applied || 0} l="Applied" onClick={() => go('applied')} />
      <Stat c="var(--amber)" v={(c.approved || 0) + (c.package_ready || 0) + (c.apply_failed || 0)} l="Pending" onClick={() => go('pending')} />
      <Stat c="var(--violet)" v={ov.total} l="Jobs checked so far" onClick={() => go('all')} />
    </div>
    <div className="charts">
      <div className="panel"><h3>Where your matches are</h3>
        <div className="bars">{ov.by_country.map(([k, v]) => <div className="bar" key={k}><span>{k}</span><i style={{ width: `${(v / maxC) * 100}%` }} /><b>{v}</b></div>)}
          {!ov.by_country.length && <span style={{ color: 'var(--muted)' }}>No matches yet.</span>}</div></div>
      <div className="panel"><h3>Visa sponsorship among matches</h3>
        <div className="stack">{order.map(k => ov.visa[k] ? <i key={k} style={{ width: `${(ov.visa[k] / visaTotal) * 100}%`, background: col[k] }} /> : null)}</div>
        <div className="legend">{order.map(k => ov.visa[k] ? <div key={k}><span style={{ '--c': col[k] }}>{VISA[k][0]}</span><b>{ov.visa[k]}</b></div> : null)}</div></div>
    </div>
    <div className="list">
      {pending.map(j => <JobRow key={j.id} j={j} onOpen={onOpen} />)}
      {!pending.length && <div className="empty">No decisions waiting. Click <b>Find new jobs now</b> to search today.</div>}
    </div>
  </>
}

function Stat({ c, v, l, onClick }) { return <button className="stat" onClick={onClick}><span className="l"><span className="dot" style={{ background: c }} />{l}</span><div className="v">{v}</div><span className="go">Open →</span></button> }

function TopMatches({ jobs, onOpen }) {
  const [min, setMin] = useState(70)
  const view = jobs.filter(j => (j.fit_score || 0) >= min)
  const bands = [100, 90, 80, 70, 60, 50, 0]
  return <>
    <div className="head"><h1>Your top {jobs.length} matches</h1><p>The best-fitting jobs the agent has found, ranked by how closely they match your CV. Drag the slider to show only the strongest ones, then open any job to apply, approve, or skip it.</p></div>
    <div className="panel slider">
      <div className="row"><b>Minimum fit: {min}</b><span style={{ color: 'var(--muted)' }}>{view.length} job{view.length === 1 ? '' : 's'} at {min} or above</span></div>
      <input type="range" min={0} max={100} step={10} value={min} onChange={e => setMin(+e.target.value)} />
      <div className="bands">{bands.map(b => <button key={b} className={min === b ? 'on' : ''} onClick={() => setMin(b)}>{b === 0 ? 'All' : `${b}+`}</button>)}</div>
    </div>
    <div className="list">
      {view.map(j => <JobRow key={j.id} j={j} onOpen={onOpen} />)}
      {!view.length && <div className="empty">No jobs score {min} or higher yet. Lower the slider or click <b>Find new jobs now</b>.</div>}
    </div>
  </>
}

function Pending({ jobs, onOpen, running }) {
  const groups = ['approved', 'package_ready', 'apply_failed']
  const [log, setLog] = useState('')
  useEffect(() => {
    const pull = () => api('/logs/approvals').then(r => setLog(r.log)).catch(() => {})
    pull(); const t = setInterval(pull, running ? 5000 : 30000); return () => clearInterval(t)
  }, [running])
  return <>
    <div className="head"><h1>Pending</h1><p>Approved jobs are applied when you click <b>Apply to approved jobs</b>. "Ready for you to submit" means the site blocked auto-apply; open the job to get the CV and the link. Failed ones can be retried with Apply now.</p></div>
    {!jobs.length && <div className="empty">Nothing pending. Approve jobs from <b>Needs your decision</b> or <b>Top matches</b>.</div>}
    {groups.map(g => { const list = jobs.filter(j => j.status === g); return list.length ? <div key={g} style={{ marginBottom: 24 }}>
      <h3 style={{ margin: '0 0 10px', fontSize: 15 }}>{STATUS[g]} <span style={{ color: 'var(--muted)', fontWeight: 500 }}>· {list.length}</span></h3>
      <div className="list">{list.map(j => <JobRow key={j.id} j={j} onOpen={onOpen} />)}</div></div> : null })}
    <div className="panel" style={{ marginTop: 10 }}>
      <h3>{running ? <><i className="spin" /> Applying now — live log</> : 'Last apply run — log'}</h3>
      <pre className="log">{log || 'No apply run yet.'}</pre>
    </div>
  </>
}

function Applied({ jobs, onOpen }) {
  return <>
    <div className="head"><h1>Applied</h1><p>Every application the agent has sent for you, newest first. Open one to see the CV that went out and any notes.</p></div>
    {!jobs.length && <div className="empty">No applications sent yet.</div>}
    <div className="list">{jobs.map(j => <JobRow key={j.id} j={j} onOpen={onOpen} sub={j.applied_at ? new Date(j.applied_at).toLocaleDateString() : ''} />)}</div>
  </>
}

function AllJobs({ jobs, onOpen }) {
  const [q, setQ] = useState(''); const [country, setCountry] = useState(''); const [visa, setVisa] = useState(''); const [status, setStatus] = useState(''); const [min, setMin] = useState(0)
  const countries = useMemo(() => [...new Set(jobs.map(j => j.country).filter(Boolean))].sort(), [jobs])
  const view = jobs.filter(j => (!q || `${j.title} ${j.company}`.toLowerCase().includes(q.toLowerCase())) && (!country || j.country === country)
    && (!visa || j.visa_status === visa) && (!status || j.status === status) && (j.fit_score || 0) >= min)
  return <>
    <div className="head"><h1>All jobs</h1><p>Every posting the agent has checked, including the ones it rejected. Filter to look for anything it might have missed.</p></div>
    <div className="filters">
      <input placeholder="Search title or company" value={q} onChange={e => setQ(e.target.value)} />
      <select value={country} onChange={e => setCountry(e.target.value)}><option value="">All countries</option>{countries.map(c => <option key={c}>{c}</option>)}</select>
      <select value={visa} onChange={e => setVisa(e.target.value)}><option value="">Any visa status</option>{Object.entries(VISA).map(([k, v]) => <option key={k} value={k}>{v[0]}</option>)}</select>
      <select value={status} onChange={e => setStatus(e.target.value)}><option value="">Any status</option>{Object.entries(STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
      <select value={min} onChange={e => setMin(+e.target.value)}>{[0, 50, 60, 70, 80, 90].map(v => <option key={v} value={v}>Fit ≥ {v}</option>)}</select>
    </div>
    <div className="panel" style={{ padding: 0, overflow: 'hidden' }}>
      <table><thead><tr><th>Title</th><th>Company</th><th>Location</th><th>Fit</th><th>Visa</th><th>Status</th></tr></thead>
        <tbody>{view.slice(0, 300).map(j => <tr className="row" key={j.id} onClick={() => onOpen(j.id)}>
          <td>{j.title}</td><td>{j.company}</td><td>{j.city ? `${j.city}, ` : ''}{j.country}</td>
          <td><span className="fit"><i style={{ width: `${j.fit_score || 0}%` }} /></span>{j.fit_score ?? '–'}</td>
          <td>{VISA[j.visa_status]?.[0] || '–'}</td><td>{STATUS[j.status] || j.status}</td></tr>)}</tbody></table>
    </div>
    <p style={{ color: 'var(--muted)', fontSize: 13 }}>{view.length} of {jobs.length} jobs{view.length > 300 ? ' (showing first 300)' : ''}</p>
  </>
}

function Drawer({ job, onClose, refresh, say }) {
  const [busy, setBusy] = useState(false); const [full, setFull] = useState(null); const [result, setResult] = useState(null)
  useEffect(() => { api(`/jobs/${job.id}`).then(setFull); setResult(null) }, [job.id])
  useEffect(() => { const k = e => e.key === 'Escape' && onClose(); window.addEventListener('keydown', k); return () => window.removeEventListener('keydown', k) }, [])
  const setStatus = async s => { await api(`/jobs/${job.id}/status`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: s }) }); await refresh(); say(s === 'approved' ? 'Approved. Click "Apply to approved jobs" when you are ready.' : 'Skipped.'); onClose() }
  const applyNow = async () => { setBusy(true); try { const r = await api(`/jobs/${job.id}/apply`, { method: 'POST' }); setResult(r); await refresh(); say(r.status === 'applied' ? 'Applied.' : 'Site needs you to submit; CV is ready.') } catch (e) { say(e.message) } setBusy(false) }
  const st = job.status
  const canApply = st !== 'applied' && !busy
  const canApprove = ['emailed', 'skipped', 'shortlisted', 'found', 'rejected', 'apply_failed', 'package_ready'].includes(st)
  const canSkip = ['emailed', 'approved', 'shortlisted', 'found', 'apply_failed', 'package_ready'].includes(st)
  const finalStatus = result?.status || job.status
  const [mail, setMail] = useState(null); const [mailBusy, setMailBusy] = useState(false)
  const openMail = async () => { setMailBusy(true); try { setMail(await api(`/jobs/${job.id}/email`)) } catch (e) { say(e.message) } setMailBusy(false) }
  const sendMail = async () => { setMailBusy(true); try { const r = await api(`/jobs/${job.id}/email`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(mail) }); say(r.note); setMail(null); await refresh(); onClose() } catch (e) { say(e.message) } setMailBusy(false) }
  return <>
    <div className="scrim" onClick={onClose} />
    <aside className="drawer" role="dialog" aria-label={job.title}>
      <div className="top"><div><h2>{job.title}</h2><div className="m">{job.company} · {job.city ? `${job.city}, ` : ''}{job.country}{job.salary ? ` · ${job.salary}` : ''}</div></div><Ring s={job.fit_score} /></div>
      <Tags j={job} />
      {job.visa_evidence && <p className="quote">Posting says: “{job.visa_evidence}”</p>}
      <div className="actions">
        {st !== 'applied' && job.contact_email && <button className="btn primary" onClick={openMail} disabled={mailBusy}>{mailBusy ? <><i className="spin" /> Drafting…</> : `Email ${job.contact_email}`}</button>}
        {st !== 'applied' && !job.contact_email && <button className="btn primary" onClick={applyNow} disabled={!canApply}>{busy ? <><i className="spin" /> Applying…</> : st === 'apply_failed' ? 'Retry apply' : 'Apply now'}</button>}
        {canApprove && <button className="btn" onClick={() => setStatus('approved')} disabled={busy}>{st === 'skipped' ? 'Un-skip & approve' : 'Approve for next run'}</button>}
        {canSkip && <button className="btn quiet" onClick={() => setStatus('skipped')} disabled={busy}>{st === 'approved' ? 'Remove from queue' : 'Skip'}</button>}
        {st === 'applied' && <span className="tag teal" style={{ alignSelf: 'center' }}>Applied{job.applied_at ? ` on ${new Date(job.applied_at).toLocaleDateString()}` : ''}</span>}
        {job.url && <a className="btn" href={job.url} target="_blank" rel="noreferrer">Open posting</a>}
        {job.cv_path && <a className="btn" href={`/api/files/cv/${job.id}`}>Tailored CV (PDF)</a>}
        {job.cv_path && <a className="btn quiet sm" href={`/api/files/cv/${job.id}?fmt=docx`}>Word</a>}
        {job.cover_letter_path && <a className="btn" href={`/api/files/cover/${job.id}`}>Cover letter</a>}
      </div>
      {mail && <div className="mail">
        <h4 style={{ marginTop: 0 }}>Review before sending</h4>
        <label>To<input value={mail.to} onChange={e => setMail({ ...mail, to: e.target.value })} /></label>
        <label>Subject<input value={mail.subject} onChange={e => setMail({ ...mail, subject: e.target.value })} /></label>
        <label>Message<textarea rows={12} value={mail.body} onChange={e => setMail({ ...mail, body: e.target.value })} /></label>
        <p style={{ color: 'var(--muted)', fontSize: 13, margin: '6px 0 10px' }}>Attached: your tailored CV (PDF){job.cover_letter_path ? ' and cover letter' : ''}. Sent from your Gmail, so replies come straight to you.</p>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn primary" onClick={sendMail} disabled={mailBusy}>{mailBusy ? <><i className="spin" /> Sending…</> : 'Send email'}</button>
          <button className="btn quiet" onClick={() => setMail(null)}>Cancel</button>
        </div>
      </div>}
      {(result || job.apply_notes) && <div className={`note ${finalStatus === 'applied' ? 'ok' : ''}`}>
        {finalStatus === 'applied' ? 'Application submitted.' : `Not auto-submitted: ${result?.apply_notes || job.apply_notes}. Open the posting and submit with the tailored CV.`}</div>}
      <div className="two">
        <div><h4>You match</h4><ul>{(job.matched_reqs || []).map((m, i) => <li key={i}>{m}</li>)}{!(job.matched_reqs || []).length && <li>—</li>}</ul></div>
        <div><h4>Gaps</h4><ul>{(job.missing_reqs || []).map((m, i) => <li key={i}>{m}</li>)}{!(job.missing_reqs || []).length && <li>None found</li>}</ul></div>
      </div>
      <h4>Job description</h4>
      <div className="desc">{full ? (full.description || '').slice(0, 6000) : 'Loading…'}</div>
      <div style={{ marginTop: 22 }}><button className="btn quiet" onClick={onClose}>Close</button></div>
    </aside>
  </>
}

function Profile({ profile, onSaved }) {
  const [file, setFile] = useState(null); const [parsed, setParsed] = useState(null); const [busy, setBusy] = useState(false); const [err, setErr] = useState('')
  const parse = async () => { setBusy(true); setErr(''); try { const fd = new FormData(); fd.append('file', file); setParsed(await api('/profile/parse', { method: 'POST', body: fd })) } catch (e) { setErr(e.message) } setBusy(false) }
  const save = async () => { await api('/profile/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(parsed) }); setParsed(null); setFile(null); onSaved() }
  return <>
    <div className="head"><h1>My CV & profile</h1><p>This is what the agent matches jobs against and builds every tailored CV from. Upload a new CV whenever it changes; the previous profile is backed up automatically.</p></div>
    <div className="profile">
      <div className="panel">
        <h3>Current profile</h3>
        <div className="kv">
          <div>Name</div><div>{profile.name}</div>
          <div>Headline</div><div>{profile.headline}</div>
          <div>Location</div><div>{profile.location}</div>
          <div>Visa</div><div>{profile.needs_visa_sponsorship ? 'Needs sponsorship' : 'No sponsorship needed'}</div>
          <div>Skills</div><div>{(profile.skills || []).length}</div>
          <div>Roles</div><div>{(profile.experience || []).map(e => e.title).join(', ')}</div>
          <div>Certifications</div><div>{(profile.certifications || []).join('; ')}</div>
        </div>
      </div>
      <div className="panel">
        <h3>Update from a new CV</h3>
        <label className="drop">
          <input type="file" accept=".pdf,.docx" onChange={e => { setFile(e.target.files[0]); setParsed(null) }} />
          {file ? <b style={{ color: 'var(--text)' }}>{file.name}</b> : <>Click to choose a PDF or Word CV</>}
        </label>
        <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
          <button className="btn primary" onClick={parse} disabled={!file || busy}>{busy ? <><i className="spin" /> Reading…</> : 'Read this CV'}</button>
        </div>
        {err && <p className="note" style={{ marginTop: 12 }}>{err}</p>}
        {parsed && <div style={{ marginTop: 16 }}>
          <p style={{ margin: '0 0 8px' }}><b>{parsed.name}</b> — {parsed.headline}</p>
          <p style={{ color: 'var(--muted)', margin: '0 0 10px', fontSize: 13.5 }}>{(parsed.skills || []).length} skills · {(parsed.experience || []).length} roles · {(parsed.certifications || []).length} certifications</p>
          <details><summary style={{ color: 'var(--muted)', cursor: 'pointer' }}>See everything extracted</summary><pre className="json">{JSON.stringify(parsed, null, 2)}</pre></details>
          <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
            <button className="btn primary" onClick={save}>Save as my profile</button>
            <button className="btn quiet" onClick={() => setParsed(null)}>Discard</button>
          </div>
        </div>}
      </div>
    </div>
  </>
}


function Paste({ onAdded }) {
  const [text, setText] = useState(''); const [busy, setBusy] = useState(false); const [err, setErr] = useState('')
  const add = async () => { setBusy(true); setErr(''); try { const j = await api('/paste', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) }); setText(''); onAdded(j) } catch (e) { setErr(e.message) } setBusy(false) }
  return <>
    <div className="head"><h1>Paste a hiring post</h1><p>Saw a post on LinkedIn, WhatsApp, or anywhere else saying "we're hiring, send your CV to…"? Paste the text here. The agent reads it, scores the fit, tailors your CV for it, and if there's an email address it drafts the application email for you to review and send.</p></div>
    <div className="panel">
      <textarea className="paste" rows={12} placeholder={"Example:\nWe're hiring a Data Analyst in Dubai. Power BI + SQL, 1-2 years experience. Visa provided. Send your CV to careers@company.com"} value={text} onChange={e => setText(e.target.value)} />
      {err && <p className="note" style={{ marginTop: 10 }}>{err}</p>}
      <div style={{ marginTop: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
        <button className="btn primary" onClick={add} disabled={busy || text.trim().length < 40}>{busy ? <><i className="spin" /> Reading, scoring and tailoring CV…</> : 'Add this job'}</button>
        <span style={{ color: 'var(--muted)', fontSize: 13 }}>Takes about a minute.</span>
      </div>
    </div>
  </>
}
