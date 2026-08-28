# Startup seeds

Every `*.json` file in this directory (or in `SEED_DIR`, when set) is applied by
`app/services/seeding.py` when the API starts. Seeding is **create-only**: a
record whose natural key already exists — agency `slug`, user `email`, client
`portal_slug`, agent `name` within its client — is left untouched, so restarts
never overwrite what was edited in the UI.

This directory ships empty. Private bootstrap data belongs outside the
repository: keep the file in a directory of your own and point `SEED_DIR` at it
(the Compose stack mounts `./work/seeds` read-only at `/app/backend/seeds`).

## Format

```jsonc
{
  "agency": { "name": "Acme", "slug": "acme", "brand_color": "#075985" },
  "users": [
    {
      "name": "Owner",
      "email": "owner@acme.com",
      "role": "superadmin",
      // Marks the user recorded as the creator of the seeded clients.
      "owner": true,
      // Read first; the bundled hash is the fallback when the variable is unset.
      "password_env": "SEED_OWNER_PASSWORD",
      "password_hash": "$2b$12$..."
    }
  ],
  // Created only when the named variable holds a key; stored encrypted.
  "provider_credentials": [
    { "provider": "openai", "base_url": "", "api_key_env": "SEED_OPENAI_API_KEY" }
  ],
  "clients": [
    {
      "name": "Acme",
      "portal_slug": "acme",
      // Any other column of the Client model may be set here.
      "agents": [
        {
          "name": "Assistant",
          "provider": "openai",
          "model": "gpt-4.1",
          // Any other column of the Agent model may be set here.
          "qa": [{ "question": "...", "answer": "...", "position": 0 }]
        }
      ]
    }
  ]
}
```

Seed files must never contain API keys or plaintext passwords: secrets come
from the environment variables named by `password_env` and `api_key_env`.
Files are applied in name order.
