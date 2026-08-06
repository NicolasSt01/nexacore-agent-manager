# OpenLivery

OpenLivery is an open source platform for an agency to build, configure and test AI agents for its clients. It can run with Docker Compose or the traditional way with FastAPI, Next.js, Baileys and PostgreSQL installed on the machine.

## What's included

- Agency and admin-user registration.
- Sign in and sign out via an `httpOnly` cookie.
- Unlimited client and agent management.
- Agency interface inspired by operational tools like Stripe, with the Geist typeface and compact tables.
- Global agent and channel views with a per-client filter, plus each client's own workspace.
- Instructions, personality, per-client context and per-agent context.
- Multi-step agent creation wizard with a live token counter and industry starter templates.
- PDF upload, text extraction, processing status and deletion.
- OpenAI-compatible connections via base URL, your own API key and model.
- Presets for common providers and an up-to-date catalog with GPT-5.6 Luna, Terra and Sol, Gemini 3.6, Claude 4.7/4.6, DeepSeek V4, Grok 4.5 and Groq models; the connection test calls `GET /models` and shows the real list available for each API key.
- API keys encrypted in PostgreSQL and always masked in the frontend.
- Playground with persistent conversations, history after reload and the sources used.
- Semantic retrieval over the knowledge base using embeddings, with keyword ranking as a fallback.
- Real WhatsApp channel through Baileys, with QR, reconnection, an encrypted persistent session and a separate number per client.
- Incoming WhatsApp messages stored in the Inbox, replies from the assigned agent and preserved knowledge sources.
- Human takeover from the agency Inbox or the client portal; human replies are sent to the real chat and the AI stays paused until control is handed back.
- Instagram, Facebook Messenger and Webchat shown as upcoming integrations.
- Agency white-label: name, identifier, color and logo stored in PostgreSQL.
- A dedicated per-client portal with its own credentials, a persistent Inbox and human/AI takeover.

## Quick start with Docker

This is the recommended way to try or ship OpenLivery. It creates four separate containers: PostgreSQL, FastAPI, Next.js and the private WhatsApp bridge with Baileys.

### Requirements

- macOS or Windows: [Docker Desktop](https://www.docker.com/products/docker-desktop/).
- Linux: Docker Engine with the Docker Compose plugin.
- Git is recommended to download and update the project, but you can also use a ZIP file.

Check that Docker is open and running:

```bash
docker --version
docker compose version
```

### Clean install

Download the project first. If it is published on Git, clone it and enter its folder:

```bash
git clone REPOSITORY_URL
cd openlivery
```

You can also download the ZIP from the repository, unzip it and open a terminal inside the folder that contains `docker-compose.yml`. Git is not required to run OpenLivery; it does make it easier to receive updates with `git pull`.

From the project root, generate a private file with random passwords and keys:

```bash
./scripts/generate-docker-env.sh
```

The script creates `.env.docker`, which is ignored by Git. Do not share it or push it to the repository. If you prefer to set the values manually, copy `.env.docker.example` to `.env.docker` and replace every text that starts with `CHANGE_`.

Build and start the app:

```bash
docker compose --env-file .env.docker up --build -d
```

On the first start Docker creates an empty database, runs the Alembic migrations and keeps the data in volumes. Check the status:

```bash
docker compose --env-file .env.docker ps
```

All four services should end up as `healthy`. Then open:

- App: [http://localhost:3000](http://localhost:3000)
- Backend: [http://localhost:8000](http://localhost:8000)
- Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- FastAPI health: [http://localhost:8000/health](http://localhost:8000/health)

The Baileys port is not published on the machine. Only FastAPI can reach the bridge through the private Compose network.

### Docker variables

| Variable | Scope | Use |
| --- | --- | --- |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Private network | Main PostgreSQL database. |
| `POSTGRES_TEST_DB` | Private network | Isolated database for `pytest`. |
| `SECRET_KEY` | Backend only | Signs the agency and portal sessions. |
| `ENCRYPTION_KEY` | Backend and persisted data | Encrypts API keys, QR and the WhatsApp session. Must not change after secrets are stored. |
| `WHATSAPP_BRIDGE_TOKEN` | Backend and Baileys | Authenticates the private communication between both containers. |
| `FRONTEND_URL` | Backend | Origin allowed by CORS; usually `http://localhost:3000`. |
| `NEXT_PUBLIC_API_URL` | Browser and frontend build | Address the browser opens to call FastAPI; usually `http://localhost:8000`. |
| `ACCESS_TOKEN_MINUTES` | Backend | Session lifetime. |
| `WHATSAPP_LOG_LEVEL` | Baileys | Log level; `silent` is recommended to avoid exposing sensitive information. |
| `API_PORT`, `WEB_PORT`, `DB_PORT` | Host | Host ports (defaults `8000` / `3000` / `5432`). Change any that clash with other local services. |
| `BIND_HOST` | Host | Bind address: `127.0.0.1` (local only) or `0.0.0.0` (expose it on a server). |

A `Makefile` wraps the common commands: `make up` (build and start everything), `make down`, `make logs`, `make migrate`, `make test`, `make help`. Ports can be overridden inline, e.g. `API_PORT=8001 WEB_PORT=3001 make up` (this keeps `NEXT_PUBLIC_API_URL` in sync automatically). With raw `docker compose`, set the same variables in `.env.docker`.

`NEXT_PUBLIC_API_URL` is baked in during `docker compose build`. If you change it, rebuild the frontend with `docker compose --env-file .env.docker build web` and start it again. Inside Docker, Compose automatically sets `db`, `api` and `whatsapp` as private hostnames; do not replace them with `localhost`.

### Day-to-day operation

View logs from all services:

```bash
docker compose --env-file .env.docker logs -f
```

View a single service:

```bash
docker compose --env-file .env.docker logs -f api
docker compose --env-file .env.docker logs -f whatsapp
```

Stop the containers without deleting data:

```bash
docker compose --env-file .env.docker stop
```

Start them again:

```bash
docker compose --env-file .env.docker start
```

Restart them and confirm the data persists:

```bash
docker compose --env-file .env.docker restart
docker compose --env-file .env.docker ps
```

Apply the migrations manually:

```bash
docker compose --env-file .env.docker exec api alembic upgrade head
```

Update after downloading a new version:

```bash
git pull
docker compose --env-file .env.docker up --build -d
```

### Tests inside Docker

With the services running:

```bash
docker compose --env-file .env.docker exec api pytest -q
docker compose --env-file .env.docker build web whatsapp
```

The second command rebuilds the validation stages: it runs the lint and build of Next.js, and the tests and the TypeScript build of the WhatsApp bridge. The final images contain only what is needed to run the app, so those development tools are not installed in the production containers.

### Backup

Create a backups folder and export PostgreSQL without stopping the app:

```bash
mkdir -p backups
docker compose --env-file .env.docker exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backups/openlivery.dump
```

Also store `.env.docker` in a separate secret manager. A backup that contains API keys or a WhatsApp session needs the same `ENCRYPTION_KEY` to be able to decrypt them.

### Restore a backup

This operation replaces data in the target database. Take another backup first and verify the file name.

```bash
docker compose --env-file .env.docker stop api whatsapp
docker compose --env-file .env.docker exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' < backups/openlivery.dump
docker compose --env-file .env.docker start api whatsapp
```

### Import an existing local PostgreSQL database

The import is optional and never happens automatically. Before starting Docker, copy into `.env.docker` the same `ENCRYPTION_KEY` value the local install uses; without that key the API keys and the WhatsApp session cannot be recovered. Also stop the local Baileys bridge to avoid two simultaneous connections with the same number.

Export the local database:

```bash
mkdir -p backups
pg_dump -h localhost -U openlivery -d openlivery -Fc > backups/openlivery-local.dump
```

With Docker already started, restore the file:

```bash
docker compose --env-file .env.docker stop api whatsapp
docker compose --env-file .env.docker exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner' < backups/openlivery-local.dump
docker compose --env-file .env.docker start api whatsapp
docker compose --env-file .env.docker exec api alembic upgrade head
```

### Delete a test install

**WARNING: the following command permanently deletes PostgreSQL, conversations, PDFs, keys and WhatsApp sessions stored in the Docker volumes. Do not run it on an install you want to keep.**

```bash
docker compose --env-file .env.docker down --volumes --remove-orphans
```

`docker compose down` without `--volumes` removes the containers and the network but keeps the persisted information.

## Traditional run without Docker

### Requirements

- macOS or Linux.
- Python 3.10 or newer.
- Node.js 20 or newer and npm.
- PostgreSQL 14 or newer running.

Docker is not required for this mode.

## 1. Prepare PostgreSQL

Open a terminal at the project root and create the user and the two local databases. If they already exist, skip the corresponding command.

```bash
psql -d postgres -c "CREATE ROLE openlivery LOGIN PASSWORD 'openlivery';"
createdb -O openlivery openlivery
createdb -O openlivery openlivery_test
```

On installs that require an explicit host, add `-h localhost` to the commands.

## 2. Configure variables

```bash
cp .env.example .env
```

Edit `.env` and change at least `SECRET_KEY` and `ENCRYPTION_KEY` to two long, random values. The `.env` file is ignored by Git.

Available variables:

| Variable | Use |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy connection to PostgreSQL. |
| `SECRET_KEY` | Session signing. |
| `ENCRYPTION_KEY` | Encryption of API keys before storing them. |
| `FRONTEND_URL` | Origin allowed by CORS. |
| `NEXT_PUBLIC_API_URL` | Public backend URL for the frontend. |
| `BACKEND_URL` | URL the Baileys bridge uses to talk to FastAPI. |
| `WHATSAPP_BRIDGE_URL` | Internal URL FastAPI uses to send commands to the bridge. |
| `WHATSAPP_BRIDGE_PORT` | Local port of the bridge; `3101` by default. |
| `WHATSAPP_BRIDGE_TOKEN` | Shared secret between FastAPI and the bridge. Must be long, random and not published. |

## 3. Install and run the backend

From the root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements.txt
cd apps/api
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

The backend runs at [http://localhost:8000](http://localhost:8000) and its interactive docs at [http://localhost:8000/docs](http://localhost:8000/docs).

## 4. Install and run the frontend

In a second terminal, from the root:

```bash
cd apps/web
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## 5. Install and run WhatsApp

In a third terminal, from the root:

```bash
cd apps/whatsapp
npm install
npm run start
```

The bridge listens only on `127.0.0.1:3101`. It does not expose the session or the QR in its logs. It must stay running alongside FastAPI to receive and send messages.

To link a number:

1. Go to **Clients** and open the client that owns the number.
2. Go to **Channels → WhatsApp → Configure**.
3. Choose one of that client's agents.
4. Click **Connect with QR code**.
5. On the phone, open WhatsApp and go to **Settings → Linked devices → Link a device**.
6. Scan the QR that OpenLivery shows and wait for the **Connected** status.

After linking it, send a message from another number to the connected phone. The conversation will appear in **Clients → client → Inbox** and in the portal Inbox. To step in, click **Take over**; while human mode is active, the agent will not reply. Click **Return to AI** to resume automation.

When the bridge restarts, it reads the enabled sessions in PostgreSQL and reconnects them automatically. There is no need to scan another QR unless WhatsApp ends the session, the device is unlinked, `ENCRYPTION_KEY` changes or **Disconnect account** is used.

## First use

1. On the initial screen, select **Create agency**.
2. Create a client and add its general context.
3. Go to **Settings** to adjust the agency identity and create an AI connection.
4. Choose a provider, enter its API key and select one of the suggested models.
5. Use **Test connection and load models** to confirm the credentials and replace the suggestions with the models returned by the provider.
6. Create an agent, assign it to the client and choose the connection.
7. Inside the agent, add manual context and upload PDFs.
8. Open **Playground**, select the agent and chat.
9. Inside **Clients → Portal**, set a URL, email and password for the client's team.
10. The client can enter its Inbox, take a conversation and hand it back to the AI agent afterwards.
11. Inside the client, open **Channels → WhatsApp** to assign the agent and link its number.

The base URL must point to the OpenAI-compatible prefix; for example, `https://api.openai.com/v1`. OpenLivery calls `POST {BASE_URL}/chat/completions` and uses `GET {BASE_URL}/models` to test the connection.

## How the knowledge is used

OpenLivery combines, in this logical order:

1. the agent's main instructions and personality;
2. the client's general context;
3. the agent's manual context;
4. text extracted from the PDFs;
5. recent conversation history.

Small knowledge bases (up to about 45,000 characters) are included in full. Larger ones are chunked and embedded when a document is uploaded, and the query retrieves the most relevant chunks by cosine similarity (up to roughly 32,000 characters). If embeddings are unavailable — for example when the provider has no embeddings endpoint — it falls back to keyword ranking. Embeddings are stored as a portable JSON vector, so no database extension is required.

The original PDFs, the extracted text, the configuration, the users and the conversations are stored in PostgreSQL.

## Tests

With PostgreSQL running and the `openlivery_test` database created:

```bash
cd apps/api
../../.venv/bin/pytest -q
```

The tests cover registration, session, main CRUD, masked key, manual context, processed PDF, conversation, sources, persistence, white-label, portal, Inbox, human takeover and loading the provider's models.

The WhatsApp channel adds tests for per-client isolation, encrypted session persistence, idempotent reception, agent reply, pause during human takeover and human sending. Also run the bridge tests and build:

```bash
cd apps/whatsapp
npm test
npm run build
```

To check the production frontend:

```bash
cd apps/web
npm run lint
npm run build
```

To re-test the migrations from scratch on the local database:

```bash
cd apps/api
alembic downgrade base
alembic upgrade head
```

## Local security

- The API key is never returned in full in backend responses.
- API keys are encrypted before storage using a key derived from `ENCRYPTION_KEY`.
- The full WhatsApp authentication state and the temporary QR are encrypted with `ENCRYPTION_KEY` before being stored in PostgreSQL.
- The browser never receives the Baileys session. It only receives the temporary QR after the agency admin is authenticated.
- FastAPI and the bridge authenticate with `WHATSAPP_BRIDGE_TOKEN`; do not reuse this value as the portal password or as an API key.
- Every channel includes `agency_id`, `client_id` and `agent_id`; the agency and portal endpoints re-check that ownership before reading or sending data.
- FastAPI and Uvicorn do not log request bodies by default.
- Do not commit `.env`, databases, logs or secrets to Git.
- For a public install, enable HTTPS, `secure` cookies, a restrictive CORS policy and securely generated keys.

## Baileys, WhatsApp Web and its limitations

Baileys is an open source library that connects to the multi-device protocol of **WhatsApp Web**. The number is linked as an additional device via QR. It does not use the official WhatsApp Business Cloud API, and this project is not affiliated with, sponsored by or endorsed by WhatsApp or Meta. Check the [official Baileys repository](https://github.com/WhiskeySockets/Baileys) before updating the dependency.

Keep these limitations and risks in mind:

- WhatsApp may change its protocol without notice; an update may require updating Baileys or re-linking the account.
- WhatsApp may end a session, replace it or revoke the device from the phone. OpenLivery tries to reconnect transient drops, but it cannot prevent a revocation.
- Unofficial use, abusive automation, spam or mass sending can lead to restrictions or suspension of the number. Only use numbers authorized by each client and respect WhatsApp's terms and the applicable regulations.
- The phone shows the session as a linked device. Anyone with access to the phone can revoke it.
- The QR lets the account be linked while it is valid: do not share it or take public screenshots.
- This first integration handles one-to-one text conversations. It ignores groups, statuses and newsletters. It can read received text and captions, but it does not yet process audio, images, documents, locations, reactions or calls.
- The bridge must stay running. There is no external queue: if it is off, WhatsApp may deliver events on reconnect, but unlimited recovery is not guaranteed.
- A single WhatsApp account belongs to one client. Another client requires a different number and a different session.

To minimize unexpected changes, `whatsapp/package.json` pins an exact Baileys version and `package-lock.json` keeps the installed tree. Before changing it, run the tests, generate a validation QR and check reception, reply, human takeover and recovery after a restart.

## Structure

```text
apps/
  api/                 FastAPI backend
    app/               API, models, routers and services
    migrations/        Alembic migrations
    tests/             Tests for the main flows
  web/                 Next.js frontend
    app/               Next.js routes
    components/        Interface, forms, Playground and Inbox
    lib/               HTTP client and model catalog
    types/             TypeScript types
  whatsapp/            Baileys bridge
    src/               Local bridge, session and receive/send
    tests/             Message-filtering tests
docker/                PostgreSQL init scripts and Docker assets
scripts/               Helper scripts (e.g. generate-docker-env.sh)
docker-compose.yml     Orchestrates all services
```

## License

MIT. See `LICENSE`.
