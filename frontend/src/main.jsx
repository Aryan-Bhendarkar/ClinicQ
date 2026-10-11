import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const FILTERS = ['all', 'scheduled', 'completed', 'cancelled'];

async function api(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === 'string') detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((d) => d.msg).join(', ');
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return res.status === 204 ? null : res.json();
}

const fmt = (iso) =>
  new Date(iso).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });

function Stat({ label, value, tone }) {
  return (
    <div className={`card stat ${tone || ''}`}>
      <span className="stat-label">{label}</span>
      <strong className="stat-value">{value}</strong>
    </div>
  );
}

function BookingModal({ doctors, onClose, onSaved }) {
  const [form, setForm] = useState({
    patient_name: '',
    patient_phone: '',
    doctor_id: doctors[0]?.id ?? '',
    scheduled_at: '',
    reason: '',
  });
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      await api('/appointments', {
        method: 'POST',
        body: JSON.stringify({
          ...form,
          doctor_id: Number(form.doctor_id),
          patient_phone: form.patient_phone || null,
          reason: form.reason || null,
          scheduled_at: new Date(form.scheduled_at).toISOString(),
        }),
      });
      onSaved();
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  return (
    <div className="overlay" onClick={onClose}>
      <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <h2>Book appointment</h2>
        <label>
          Patient name
          <input required minLength={2} value={form.patient_name} onChange={set('patient_name')} />
        </label>
        <label>
          Phone
          <input value={form.patient_phone} onChange={set('patient_phone')} />
        </label>
        <label>
          Doctor
          <select required value={form.doctor_id} onChange={set('doctor_id')}>
            {doctors.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} - {d.specialty}
              </option>
            ))}
          </select>
        </label>
        <label>
          Date and time
          <input required type="datetime-local" value={form.scheduled_at} onChange={set('scheduled_at')} />
        </label>
        <label>
          Reason
          <textarea rows={3} value={form.reason} onChange={set('reason')} />
        </label>
        {error && <p className="error">{error}</p>}
        <div className="actions">
          <button type="button" className="btn ghost" onClick={onClose}>
            Cancel
          </button>
          <button className="btn primary" disabled={saving}>
            {saving ? 'Saving...' : 'Book'}
          </button>
        </div>
      </form>
    </div>
  );
}

function App() {
  const [appointments, setAppointments] = useState([]);
  const [doctors, setDoctors] = useState([]);
  const [stats, setStats] = useState(null);
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modal, setModal] = useState(false);

  const load = useCallback(async () => {
    try {
      const [a, d, s] = await Promise.all([
        api('/appointments'),
        api('/doctors'),
        api('/appointments/stats'),
      ]);
      setAppointments(a);
      setDoctors(d);
      setStats(s);
      setError('');
    } catch (err) {
      setError(`Cannot reach the ClinicQ API: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const visible = useMemo(
    () => (filter === 'all' ? appointments : appointments.filter((a) => a.status === filter)),
    [appointments, filter],
  );

  async function setStatus(id, status) {
    try {
      await api(`/appointments/${id}`, { method: 'PUT', body: JSON.stringify({ status }) });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function remove(id) {
    if (!window.confirm('Delete this appointment permanently?')) return;
    try {
      await api(`/appointments/${id}`, { method: 'DELETE' });
      load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          <span className="logo">+</span> ClinicQ
        </div>
        <nav>
          <a className="active">Appointments</a>
          <a>Doctors ({doctors.length})</a>
        </nav>
        <div className="side-foot">Clinic front-desk console</div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>Appointments</h1>
            <p className="muted">Manage today&apos;s schedule and upcoming visits.</p>
          </div>
          <button className="btn primary" disabled={!doctors.length} onClick={() => setModal(true)}>
            + Book appointment
          </button>
        </header>

        {error && <div className="banner">{error}</div>}

        <section className="stats">
          <Stat label="Total" value={stats?.total ?? '-'} />
          <Stat label="Scheduled" value={stats?.scheduled ?? '-'} tone="blue" />
          <Stat label="Completed" value={stats?.completed ?? '-'} tone="green" />
          <Stat label="Cancelled" value={stats?.cancelled ?? '-'} tone="red" />
          <Stat label="Today" value={stats?.today ?? '-'} tone="amber" />
        </section>

        <section className="card">
          <div className="filters">
            {FILTERS.map((f) => (
              <button key={f} className={`chip ${filter === f ? 'on' : ''}`} onClick={() => setFilter(f)}>
                {f}
              </button>
            ))}
          </div>

          {loading ? (
            <p className="muted pad">Loading appointments...</p>
          ) : visible.length === 0 ? (
            <p className="muted pad">No appointments match this filter.</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Patient</th>
                    <th>Doctor</th>
                    <th>When</th>
                    <th>Reason</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {visible.map((a) => (
                    <tr key={a.id}>
                      <td>
                        <strong>{a.patient_name}</strong>
                        <div className="muted small">{a.patient_phone || ''}</div>
                      </td>
                      <td>
                        {a.doctor.name}
                        <div className="muted small">{a.doctor.specialty}</div>
                      </td>
                      <td>{fmt(a.scheduled_at)}</td>
                      <td className="reason">{a.reason || '-'}</td>
                      <td>
                        <span className={`badge ${a.status}`}>{a.status}</span>
                      </td>
                      <td className="row-actions">
                        {a.status === 'scheduled' && (
                          <>
                            <button className="link" onClick={() => setStatus(a.id, 'completed')}>
                              Complete
                            </button>
                            <button className="link warn" onClick={() => setStatus(a.id, 'cancelled')}>
                              Cancel
                            </button>
                          </>
                        )}
                        <button className="link warn" onClick={() => remove(a.id)}>
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>

      {modal && (
        <BookingModal
          doctors={doctors}
          onClose={() => setModal(false)}
          onSaved={() => {
            setModal(false);
            load();
          }}
        />
      )}
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
