import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../api/client';
import { ENV_LABEL, LIVE_ENVIRONMENTS, PROVIDERS } from '../utils/constants';
import Icon from './Icon';
import { ErrorBox, Modal, Skeleton } from './ui';

const isVisible = (field, values) => !field.show_when || Object.entries(field.show_when).every(([k, v]) => values[k] === v);

/** Returns { fieldName: message } for what can be checked before calling the cloud. */
export function validateFields(fields, values, secretsSet = {}) {
  const errors = {};
  fields.filter((f) => isVisible(f, values)).forEach((f) => {
    const value = (values[f.name] || '').trim();
    if (!value) {
      if (f.required && !secretsSet[f.name]) errors[f.name] = `${f.label} is required`;
    } else if (f.pattern && !new RegExp(f.pattern).test(value)) {
      errors[f.name] = `${f.label} has an invalid format`;
    }
  });
  return errors;
}

function FieldInput({ field, value, saved, error, onChange }) {
  const id = `cfg-${field.name}`;
  const common = { id, value, 'aria-invalid': error ? 'true' : undefined, 'aria-describedby': field.help ? `${id}-help` : undefined, onChange: (e) => onChange(e.target.value) };
  const savedHint = saved ? 'Saved. Leave blank to keep it.' : '';

  function readFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    file.text().then(onChange);
  }

  return (
    <div className="field">
      <label className="label" htmlFor={id}>{field.label}{field.required ? '' : ' (optional)'}</label>
      {field.type === 'select' && (
        <select className="select" {...common}>
          {field.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      )}
      {field.type === 'text' && <input className="input mono" type="text" autoComplete="off" spellCheck={false} placeholder={field.placeholder || ''} {...common} />}
      {field.type === 'secret' && <input className="input mono" type="password" autoComplete="new-password" placeholder={savedHint} {...common} />}
      {field.type === 'secret_text' && (
        <>
          <textarea className="input masked" rows={4} spellCheck={false} placeholder={savedHint} {...common} />
          <input type="file" accept=".json,application/json" aria-label={`Choose ${field.label} file`} onChange={readFile} />
        </>
      )}
      {field.help && <span className="field-help" id={`${id}-help`}>{field.help}</span>}
      {error && <span className="field-error" role="alert">{error}</span>}
    </div>
  );
}

function TestResult({ result }) {
  return (
    <div className={result.ok ? 'notice' : 'error-box'} role="status">
      <strong>{result.ok ? `Connection validated${result.account ? ` · ${result.account}` : ''}` : 'Connection failed'}</strong>
      {result.checks?.length ? (
        <ul className="check-list">
          {result.checks.map((c) => (
            <li key={c.name}>
              <span className={c.ok ? 'ok' : 'bad'}><Icon name={c.ok ? 'check' : 'warning'} size={15} /></span>
              <span><strong>{c.name}.</strong> {c.detail}</span>
            </li>
          ))}
        </ul>
      ) : !result.ok && <div style={{ marginTop: 6 }}>{result.message}</div>}
    </div>
  );
}

/** Configuration form for one cloud and environment: enter the fields, test the connection, then save. */
export default function CloudConfigModal({ provider, reason, onClose, onChanged }) {
  const [environment, setEnvironment] = useState(LIVE_ENVIRONMENTS[0]);
  const [view, setView] = useState(null);
  const [values, setValues] = useState({});
  const [errors, setErrors] = useState({});
  const [loadError, setLoadError] = useState(null);
  const [failure, setFailure] = useState('');
  const [result, setResult] = useState(null);
  const [testedValues, setTestedValues] = useState(null);
  const [busy, setBusy] = useState('');
  const resultRef = useRef(null);
  const name = PROVIDERS.find((p) => p.value === provider)?.name;

  useEffect(() => {
    let current = true;
    setErrors({});
    setResult(null);
    setFailure('');
    setTestedValues(null);
    api.get(`/cloud-accounts/${provider}`, { environment })
      .then((v) => { if (current) { setView(v); setValues(v.values); } })
      .catch(setLoadError);
    return () => { current = false; };
  }, [provider, environment]);

  useEffect(() => {
    if (result || failure) resultRef.current?.scrollIntoView?.({ block: 'nearest' });
  }, [result, failure]);

  const fields = useMemo(() => (view?.fields || []).filter((f) => isVisible(f, values)), [view, values]);
  // Save stays off until the values on screen are the ones that passed the test
  const canSave = result?.ok && testedValues === JSON.stringify(values);

  function setField(fieldName, value) {
    setValues((v) => ({ ...v, [fieldName]: value }));
    setErrors((e) => ({ ...e, [fieldName]: undefined }));
    setResult(null);
    setFailure('');
  }

  async function test() {
    const found = validateFields(view.fields, values, view.secrets_set);
    setErrors(found);
    setResult(null);
    setFailure('');
    const firstInvalid = view.fields.find((f) => found[f.name]);
    if (firstInvalid) {
      document.getElementById(`cfg-${firstInvalid.name}`)?.focus();
      return;
    }
    setBusy('test');
    try {
      const r = await api.post(`/cloud-accounts/${provider}/test`, { environment, config: values });
      setResult(r);
      setTestedValues(JSON.stringify(values));
    } catch (e) {
      setFailure(e.message);
    } finally {
      setBusy('');
    }
  }

  async function save(activate) {
    setBusy('save');
    setFailure('');
    try {
      await api.put(`/cloud-accounts/${provider}/config`, { environment, config: values, activate });
      onChanged(activate ? `${name} switched to Live. Loading its data now.` : `${name} ${ENV_LABEL[environment]} configuration saved`);
      onClose();
    } catch (e) {
      setFailure(e.message);
    } finally {
      setBusy('');
    }
  }

  async function remove() {
    const last = view.connections.length === 1;
    if (!window.confirm(`Remove the ${name} ${ENV_LABEL[environment]} configuration? Its data stops showing.${last ? ' This is the last one, so the cloud goes back to Mock.' : ''}`)) return;
    setBusy('remove');
    try {
      await api.del(`/cloud-accounts/${provider}/config?environment=${environment}`);
      onChanged(`${name} ${ENV_LABEL[environment]} configuration removed`);
      onClose();
    } catch (e) {
      setFailure(e.message);
      setBusy('');
    }
  }

  return (
    <Modal
      title={`Configure ${name}`}
      onClose={onClose}
      actions={view && (
        <>
          {view.has_saved_config && <button type="button" className="btn danger" style={{ marginRight: 'auto' }} disabled={!!busy} onClick={remove}><Icon name="trash" size={15} /> Remove</button>}
          <button type="button" className="btn" onClick={onClose}>Cancel</button>
          <button type="button" className="btn" disabled={!!busy} onClick={test}>{busy === 'test' ? 'Testing…' : 'Test connection'}</button>
          <button type="button" className="btn" disabled={!canSave || !!busy} onClick={() => save(false)}>Save</button>
          {view.mode !== 'live' && <button type="button" className="btn primary" disabled={!canSave || !!busy} onClick={() => save(true)}>Save and use Live</button>}
        </>
      )}
    >
      <ErrorBox error={loadError} />
      {!view && !loadError && <Skeleton height={260} />}
      {view && (
        <>
          {reason && <div className="notice" style={{ marginBottom: 12 }}>{reason}</div>}
          {view.secrets_unreadable && <div className="error-box" style={{ marginBottom: 12 }}>The saved secret cannot be decrypted because the encryption key changed. Enter it again.</div>}
          <div className="tiny"><strong>Before you start</strong></div>
          <ul className="prereq">{view.prerequisites.map((p) => <li key={p}>{p}</li>)}</ul>
          <form className="config-form" autoComplete="off" onSubmit={(e) => { e.preventDefault(); test(); }}>
            <div className="field">
              <label className="label" htmlFor="cfg-environment">Environment</label>
              <select id="cfg-environment" className="select" value={environment} disabled={!!busy} onChange={(e) => setEnvironment(e.target.value)}>
                {LIVE_ENVIRONMENTS.map((env) => <option key={env} value={env}>{ENV_LABEL[env]}{view.connections.some((c) => c.environment === env) ? ' (configured)' : ''}</option>)}
              </select>
              <span className="field-help">This account's cost and resources appear under this environment on every screen. Each environment needs its own account.</span>
            </div>
            {fields.map((f) => (
              <FieldInput key={f.name} field={f} value={values[f.name] || ''} saved={view.secrets_set[f.name]} error={errors[f.name]} onChange={(v) => setField(f.name, v)} />
            ))}
          </form>
          <p className="tiny" style={{ marginTop: 12 }}>{view.cost_note} Secrets are encrypted before they are stored and are never shown again.</p>
          <div ref={resultRef} className="test-result">
            {failure && <div className="error-box" role="alert" style={{ marginTop: 12 }}>{failure}</div>}
            {result && <div style={{ marginTop: 12 }}><TestResult result={result} /></div>}
          </div>
        </>
      )}
    </Modal>
  );
}
