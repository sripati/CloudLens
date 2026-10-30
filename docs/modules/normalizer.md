# Module: Normalizer

**Path:** `backend/app/services/normalizer.py`

Turns provider-specific vocabulary into the CloudLens vocabulary so the three clouds can be compared.

## Vocabularies

| Constant | Values |
|---|---|
| `PROVIDERS` | aws, azure, gcp |
| `RESOURCE_TYPES` | compute, containers, database, storage, networking, other |
| `ENVIRONMENTS` | production, staging, development, unassigned |

## Functions

| Function | Behaviour |
|---|---|
| `classify_service(name)` | Ordered regex rules (`_SERVICE_RULES`); the first match wins. Containers are checked before compute so "Elastic **Kubernetes** Service" is not classed as EC2. Unknown → `other`. |
| `normalize_environment(value)` | Handles the AWS `environment$prod` form, exact aliases (`prod`, `prd`, `live` → production; `stg`, `uat`, `qa` → staging; `dev`, `test`, `sandbox` → development), then substring matches; empty → `unassigned`. |
| `normalize_region(value)` | Lower-case; "No Region", empty → `global`. |
| `to_usd(amount, currency, inr_rate, conversion_rate)` | USD unchanged. GCP passes its own export `currency_conversion_rate`; INR uses the Settings rate. |

## Extending

- New service names: add a pattern to the correct tuple in `_SERVICE_RULES`, then a case to
  `tests/test_normalizer.py::test_classify_service`.
- New environment alias: add it to `_ENV_ALIASES`.
- A new resource type requires updating `RESOURCE_TYPES`, the frontend `constants.js`, and the
  schemas' validators.
