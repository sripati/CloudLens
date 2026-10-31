import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../api/client';
import CloudConfigModal, { validateFields } from './CloudConfigModal';

vi.mock('../api/client', () => ({ api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), del: vi.fn() } }));

const FIELDS = [
  { name: 'auth_method', label: 'Authentication', type: 'select', required: true, options: [{ value: 'access_keys', label: 'Keys' }, { value: 'default_chain', label: 'Chain' }] },
  { name: 'access_key_id', label: 'Access key ID', type: 'text', required: true, pattern: '^[A-Z0-9]{16,128}$', show_when: { auth_method: 'access_keys' } },
  { name: 'secret_access_key', label: 'Secret access key', type: 'secret', required: true, show_when: { auth_method: 'access_keys' } },
  { name: 'regions', label: 'Regions', type: 'text', required: true },
];
const VIEW = {
  provider: 'aws', mode: 'mock', fields: FIELDS, values: { auth_method: 'access_keys', access_key_id: '', regions: 'ap-south-1' },
  secrets_set: { secret_access_key: false }, secrets_unreadable: false, has_saved_config: false, verified: false, connections: [],
  prerequisites: ['Enable Cost Explorer'], cost_note: 'Each test costs $0.01.',
};
const OK = { ok: true, account: '111122223333', message: 'Connected', checks: [{ name: 'Cost Explorer', ok: true, detail: 'Cost data is readable' }] };

function fill(label, value) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

async function openForm(props = {}) {
  api.get.mockResolvedValue(VIEW);
  render(<CloudConfigModal provider="aws" onClose={() => {}} onChanged={() => {}} {...props} />);
  await screen.findByLabelText('Access key ID');
}

function fillValid() {
  fill('Access key ID', 'AKIAABCDEFGHIJKLMNOP');
  fill('Secret access key', 'shh');
}

beforeEach(() => vi.clearAllMocks());

describe('validateFields', () => {
  it('requires visible fields only', () => {
    expect(Object.keys(validateFields(FIELDS, { auth_method: 'default_chain', regions: 'r' }))).toEqual([]);
    expect(Object.keys(validateFields(FIELDS, { auth_method: 'access_keys', regions: 'r' }))).toEqual(['access_key_id', 'secret_access_key']);
  });
  it('checks the pattern and accepts an already saved secret', () => {
    const errors = validateFields(FIELDS, { auth_method: 'access_keys', access_key_id: 'bad', regions: 'r' }, { secret_access_key: true });
    expect(errors).toEqual({ access_key_id: 'Access key ID has an invalid format' });
  });
});

describe('CloudConfigModal', () => {
  it('does not call the cloud when required fields are missing', async () => {
    await openForm();
    fireEvent.click(screen.getByRole('button', { name: 'Test connection' }));
    expect(await screen.findByText('Access key ID is required')).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('hides key fields for the default credential chain', async () => {
    await openForm();
    fill('Authentication', 'default_chain');
    expect(screen.queryByLabelText('Access key ID')).toBeNull();
  });

  it('keeps Save off until the test passes, then saves and activates', async () => {
    const onChanged = vi.fn();
    await openForm({ onChanged });
    const save = screen.getByRole('button', { name: 'Save and use Live' });
    expect(save).toBeDisabled();
    fillValid();
    api.post.mockResolvedValue(OK);
    fireEvent.click(screen.getByRole('button', { name: 'Test connection' }));
    expect(await screen.findByText(/Connection validated/)).toBeInTheDocument();
    expect(save).toBeEnabled();
    api.put.mockResolvedValue(VIEW);
    fireEvent.click(save);
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
    expect(api.put).toHaveBeenCalledWith('/cloud-accounts/aws/config', expect.objectContaining({ activate: true, environment: 'production' }));
  });

  it('turns Save off again when a value changes after a passed test', async () => {
    await openForm();
    fillValid();
    api.post.mockResolvedValue(OK);
    fireEvent.click(screen.getByRole('button', { name: 'Test connection' }));
    await screen.findByText(/Connection validated/);
    fill('Regions', 'us-east-1');
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
    expect(screen.queryByText(/Connection validated/)).toBeNull();
  });

  it('shows each failed check and keeps Save off', async () => {
    await openForm();
    fillValid();
    api.post.mockResolvedValue({ ok: false, message: 'x', checks: [{ name: 'Cost Explorer', ok: false, detail: 'Enable it in Billing' }] });
    fireEvent.click(screen.getByRole('button', { name: 'Test connection' }));
    expect(await screen.findByText(/Enable it in Billing/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
  });

  it('asks for an environment, loads its own values and marks configured ones', async () => {
    api.get.mockImplementation((path, params) => Promise.resolve({ ...VIEW, connections: [{ environment: 'production', account: '1', verified: true }], values: { ...VIEW.values, regions: params.environment === 'staging' ? 'us-east-1' : 'ap-south-1' } }));
    render(<CloudConfigModal provider="aws" onClose={() => {}} onChanged={() => {}} />);
    await screen.findByLabelText('Access key ID');
    expect(screen.getByRole('option', { name: 'Production (configured)' })).toBeInTheDocument();
    fill('Environment', 'staging');
    await waitFor(() => expect(screen.getByLabelText('Regions')).toHaveValue('us-east-1'));
    expect(api.get).toHaveBeenLastCalledWith('/cloud-accounts/aws', { environment: 'staging' });
    api.post.mockResolvedValue(OK);
    fillValid();
    fireEvent.click(screen.getByRole('button', { name: 'Test connection' }));
    await screen.findByText(/Connection validated/);
    expect(api.post).toHaveBeenCalledWith('/cloud-accounts/aws/test', expect.objectContaining({ environment: 'staging' }));
  });
});
