import { useState } from 'react';
import { api } from '../api/client';
import Icon from '../components/Icon';
import PageHeader from '../components/PageHeader';
import { Badge, Card, ErrorBox, Modal, Skeleton, Toast } from '../components/ui';
import { useAuth } from '../context/AuthContext';
import { useApi } from '../hooks/useApi';
import { dateTime } from '../utils/format';

function UserForm({ initial, onClose, onSaved }) {
  const editing = Boolean(initial?.id);
  const [form, setForm] = useState({ email: '', full_name: '', role: 'viewer', is_active: true, ...initial, password: '' });
  const [err, setErr] = useState(null);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value });
  async function save() {
    setErr(null);
    try {
      if (editing) {
        const body = { full_name: form.full_name, role: form.role, is_active: form.is_active };
        if (form.password) body.password = form.password;
        await api.patch(`/users/${initial.id}`, body);
      } else {
        await api.post('/users', { email: form.email, full_name: form.full_name, password: form.password, role: form.role });
      }
      onSaved(editing ? 'User updated' : 'User created');
    } catch (e) {
      setErr(e);
    }
  }
  return (
    <Modal title={editing ? `Edit ${initial.email}` : 'Add user'} onClose={onClose}
      actions={<><button type="button" className="btn" onClick={onClose}>Cancel</button><button type="button" className="btn primary" onClick={save}>Save</button></>}>
      <ErrorBox error={err} />
      <div className="form-grid" style={{ marginTop: err ? 12 : 0 }}>
        {!editing && <div className="field"><label className="label" htmlFor="u-email">Email</label><input id="u-email" type="email" className="input" value={form.email} onChange={set('email')} autoComplete="off" /></div>}
        <div className="field"><label className="label" htmlFor="u-name">Full name</label><input id="u-name" className="input" value={form.full_name} onChange={set('full_name')} /></div>
        <div className="field"><label className="label" htmlFor="u-pw">{editing ? 'New password (optional)' : 'Password (min 8)'}</label><input id="u-pw" type="password" className="input" value={form.password} onChange={set('password')} autoComplete="new-password" /></div>
        <div className="field"><label className="label" htmlFor="u-role">Role</label>
          <select id="u-role" className="select" value={form.role} onChange={set('role')}><option value="viewer">Viewer · read-only</option><option value="admin">Admin · full access</option></select></div>
        {editing && <label style={{ display: 'flex', gap: 10, alignItems: 'center', minHeight: 44 }}><input type="checkbox" checked={form.is_active} onChange={set('is_active')} style={{ width: 18, height: 18 }} /> Active</label>}
      </div>
    </Modal>
  );
}

export default function UsersPage() {
  const { user: me } = useAuth();
  const users = useApi('/users');
  const [editing, setEditing] = useState(null);
  const [toast, setToast] = useState('');
  return (
    <>
      <PageHeader title="Users & Roles" subtitle="Admins manage rules, accounts and settings; viewers have read-only access">
        <button type="button" className="btn primary" onClick={() => setEditing({})}><Icon name="plus" size={16} strokeWidth={2} /> Add user</button>
      </PageHeader>
      <ErrorBox error={users.error} onRetry={users.reload} />
      <Card title="Role permissions">
        <div className="table-wrap">
          <table className="data">
            <thead><tr><th>Capability</th><th>Admin</th><th>Viewer</th></tr></thead>
            <tbody>
              {[
                ['View dashboard, costs, resources, reports', true, true],
                ['Export CSV reports', true, true],
                ['Acknowledge alert events', true, true],
                ['Create / edit / delete alert rules', true, false],
                ['Send test notifications', true, false],
                ['Trigger syncs, test cloud connections', true, false],
                ['Edit budget, exchange rate, channels', true, false],
                ['Manage users', true, false],
              ].map(([c, a, v]) => (
                <tr key={c}><td>{c}</td><td>{a ? <Badge kind="ok">Yes</Badge> : <Badge>No</Badge>}</td><td>{v ? <Badge kind="ok">Yes</Badge> : <Badge>No</Badge>}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <Card title="Users">
        {!users.data ? <Skeleton height={160} /> : (
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Last login</th><th>Created</th><th><span className="sr-only">Actions</span></th></tr></thead>
              <tbody>
                {users.data.map((u) => (
                  <tr key={u.id}>
                    <td style={{ fontWeight: 600 }}>{u.full_name || '–'}{u.id === me?.id && <span className="tiny"> (you)</span>}</td>
                    <td className="mono">{u.email}</td>
                    <td><Badge kind={u.role}>{u.role}</Badge></td>
                    <td><Badge kind={u.is_active ? 'ok' : 'neutral'}>{u.is_active ? 'Active' : 'Disabled'}</Badge></td>
                    <td className="tiny">{dateTime(u.last_login_at)}</td>
                    <td className="tiny">{dateTime(u.created_at)}</td>
                    <td>
                      <span style={{ display: 'inline-flex', gap: 6 }}>
                        <button type="button" className="btn small" aria-label={`Edit ${u.email}`} onClick={() => setEditing(u)}><Icon name="edit" size={15} /></button>
                        {u.id !== me?.id && (
                          <button type="button" className="btn small danger" aria-label={`Delete ${u.email}`}
                            onClick={async () => { if (!window.confirm(`Delete ${u.email}?`)) return; try { await api.del(`/users/${u.id}`); setToast('User deleted'); users.reload(); } catch (e) { setToast(e.message); } }}>
                            <Icon name="trash" size={15} />
                          </button>
                        )}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      {editing && <UserForm initial={editing} onClose={() => setEditing(null)} onSaved={(m) => { setEditing(null); setToast(m); users.reload(); }} />}
      <Toast message={toast} onDone={() => setToast('')} />
    </>
  );
}
