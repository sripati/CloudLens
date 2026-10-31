# Screen Documentation

One file per screen: purpose, layout, data sources, interactions, role differences, and extension notes.
Screenshots are in [../screenshots/](../screenshots/) (dark and light).

| Route | Screen | Roles | Doc |
|---|---|---|---|
| `/login` | Login | public | [login.md](login.md) |
| `/` | Dashboard | all | [dashboard.md](dashboard.md) |
| `/costs` | Cost Explorer | all | [cost-explorer.md](cost-explorer.md) |
| `/resources` | Resources | all | [resources.md](resources.md) |
| `/resources/:id` | Resource detail | all | [resource-detail.md](resource-detail.md) |
| `/alerts` | Alerts | all (edit: admin) | [alerts.md](alerts.md) |
| `/reports` | Reports | all | [reports.md](reports.md) |
| `/accounts` | Cloud Accounts | admin | [cloud-accounts.md](cloud-accounts.md) |
| `/users` | Users & Roles | admin | [users.md](users.md) |
| `/settings` | Settings | all (edit: admin) | [settings.md](settings.md) |

## Common elements (every screen except Login)

- **Sidebar:** navigation (admin-only items hidden for viewers), red badge with the number of firing
  alerts, and the *Cloud connections* box (per-provider status, mock/live, `DATA_SOURCE`).
- **Page header:** title and subtitle, page actions, the **USD $ / INR ₹** toggle, the **Light/Dark mode** toggle,
  and the user chip (name, role, sign out).
- **Filter bar** (Dashboard, Cost Explorer, Resources): provider segmented control, environment and
  resource-type selects, the **date-range calendar** (quick ranges computed from today, or a validated custom range;
  see [dashboard.md](dashboard.md#date-range-picker)), and *Reset filters*.
  Filters are shared between these screens for the browser session.
- Layout is responsive: at phone width the sidebar stacks on top, cards wrap, and tables scroll sideways.
