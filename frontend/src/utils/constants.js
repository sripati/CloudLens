export const PROVIDERS = [
  { value: 'aws', label: 'AWS', name: 'Amazon Web Services', color: 'var(--aws)' },
  { value: 'azure', label: 'Azure', name: 'Microsoft Azure', color: 'var(--azure)' },
  { value: 'gcp', label: 'GCP', name: 'Google Cloud', color: 'var(--gcp)' },
];
export const PROVIDER_LABEL = { aws: 'AWS', azure: 'Azure', gcp: 'GCP' };
export const PROVIDER_COLOR = { aws: 'var(--aws)', azure: 'var(--azure)', gcp: 'var(--gcp)' };

export const ENVIRONMENTS = [
  { value: 'production', label: 'Production' },
  { value: 'staging', label: 'Staging' },
  { value: 'development', label: 'Development' },
  { value: 'unassigned', label: 'Unassigned' },
];
export const ENV_LABEL = { production: 'Production', staging: 'Staging', development: 'Development', unassigned: 'Unassigned' };

export const RESOURCE_TYPES = [
  { value: 'compute', label: 'Compute' },
  { value: 'containers', label: 'Containers' },
  { value: 'database', label: 'Database' },
  { value: 'storage', label: 'Storage' },
  { value: 'networking', label: 'Networking' },
  { value: 'other', label: 'Other' },
];
export const TYPE_LABEL = Object.fromEntries(RESOURCE_TYPES.map((t) => [t.value, t.label]));

export const STATUS_LABEL = { healthy: 'Healthy', idle: 'Idle', over_utilized: 'Over-utilized', no_metrics: 'No metrics' };


// Colors for non-provider series (environment / type / service breakdowns).
// Ordered so neighbours differ in lightness, not only hue.
export const SERIES_COLORS = ['#5B9BFF', '#F5A524', '#34D399', '#F472B6', '#A78BFA', '#94A3B8', '#FB7185', '#22D3EE'];

export const ACTION_LABEL = {
  stop_idle: 'Stop / schedule',
  rightsize: 'Rightsize',
  schedule: 'Off-hours schedule',
  storage_tier: 'Storage tiering',
};
