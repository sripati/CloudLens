import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useAuth } from '../context/AuthContext';
import { usePrefs } from '../context/PrefsContext';
import { useApi } from '../hooks/useApi';
import ReportsPage from '../pages/ReportsPage';
import { defaultBounds } from '../utils/dates';
import FilterBar from './FilterBar';
import Layout from './Layout';
import PageHeader from './PageHeader';

vi.mock('../context/AuthContext', () => ({ useAuth: vi.fn() }));
vi.mock('../context/PrefsContext', () => ({ usePrefs: vi.fn() }));
vi.mock('../hooks/useApi', () => ({ useApi: vi.fn() }));
vi.mock('../api/client', () => ({ api: { download: vi.fn() } }));

const FILTER_QUERY = { provider: 'aws', environment: 'staging', resource_type: 'compute', start: '2026-10-01', end: '2026-10-31' };

beforeEach(() => {
  vi.clearAllMocks();
  useApi.mockReturnValue({ data: null });
  useAuth.mockReturnValue({ user: { full_name: 'Asha Rao', email: 'a@x.io' }, isAdmin: true, logout: vi.fn() });
  usePrefs.mockReturnValue({
    refreshSettings: vi.fn(), refreshBounds: vi.fn(), filters: { provider: 'aws', environment: 'staging', resource_type: 'compute', range: { preset: 'this_month' } },
    range: { start: '2026-10-01', end: '2026-10-31', preset: 'this_month', label: 'This month', days: 31 }, bounds: defaultBounds(), boundsReady: true,
    filterQuery: FILTER_QUERY, setFilters: vi.fn(), resetFilters: vi.fn(), setRange: vi.fn(), fmt: String, fmtCompact: String,
  });
});

function renderLayout() {
  render(<MemoryRouter><Layout /></MemoryRouter>);
}

describe('user bar', () => {
  it('shows the signed-in administrator and logs out', () => {
    const logout = vi.fn();
    useAuth.mockReturnValue({ user: { full_name: 'Asha Rao' }, isAdmin: true, logout });
    renderLayout();
    expect(screen.getByText('Asha Rao')).toBeInTheDocument();
    expect(screen.getByText('Administrator')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Logout' }));
    expect(logout).toHaveBeenCalled();
  });

  it('shows a viewer as Viewer', () => {
    useAuth.mockReturnValue({ user: { email: 'v@x.io' }, isAdmin: false, logout: vi.fn() });
    renderLayout();
    expect(screen.getByText('Viewer')).toBeInTheDocument();
    expect(screen.queryByText('Administrator')).not.toBeInTheDocument();
  });
});

describe('page header', () => {
  it('has only the title and the page actions: no currency, theme or user controls', () => {
    render(<PageHeader title="Reports"><button type="button">Download CSV</button></PageHeader>);
    expect(screen.getByRole('button', { name: 'Download CSV' })).toBeInTheDocument();
    expect(screen.getAllByRole('button')).toHaveLength(1);
  });
});

describe('filter bar', () => {
  it('offers All, Production, Staging and Development, and not Unassigned', () => {
    render(<FilterBar />);
    const options = within(screen.getByLabelText('Environment')).getAllByRole('option').map((o) => o.textContent);
    expect(options).toEqual(['All environments', 'Production', 'Staging', 'Development']);
  });
});

describe('reports screen', () => {
  it('uses the shared filters and keeps only the download and print actions', () => {
    render(<MemoryRouter><ReportsPage /></MemoryRouter>);
    expect(screen.getByRole('region', { name: 'Filters' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Download CSV/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Print \/ PDF/ })).toBeInTheDocument();
    expect(useApi).toHaveBeenCalledWith('/reports/summary', FILTER_QUERY, { enabled: true });
    expect(screen.queryByText('USD $')).not.toBeInTheDocument();
    expect(screen.queryByText(/Light mode|Dark mode/)).not.toBeInTheDocument();
  });
});
