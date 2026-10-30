# secrets/

This folder is mounted read-only into the backend container at `/secrets`.
Everything except this README is ignored by git.

Put the GCP service-account key here as `gcp-key.json` and set this in `.env`:

```
GOOGLE_APPLICATION_CREDENTIALS=/secrets/gcp-key.json
```

Never commit credentials. On EC2, prefer an IAM instance role for AWS (`AWS_USE_DEFAULT_CREDENTIALS=true`).
