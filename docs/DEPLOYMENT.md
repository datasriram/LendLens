# Deploy the LendLens demo

The Streamlit server calls FastAPI over HTTPS. FastAPI loads the existing FastEmbed
models and accesses the existing Qdrant Cloud collection and Groq. The browser
never receives the backend bearer token or the provider credentials. Browser CORS
is closed because Streamlit makes the API requests server-side.

## 1. Publish the reviewed changes

Review the local diff. Commit the deployment files on a branch you control and push
it to `datasriram/LendLens`. Use that branch on both hosts. Keep the files under
`evaluation/`, local databases, reports and secret files out of the commit.

## 2. Deploy FastAPI on Render

1. Sign into [Render](https://dashboard.render.com/) and authorize its GitHub app
   for `datasriram/LendLens`. Enable billing in your workspace for the paid service.
2. Create a **Blueprint** from the repository and reviewed branch. The included
   `render.yaml` creates one Docker worker with 2 GB RAM and a `/health` check.
   Automatic deploys are disabled so you can choose when to update the demo.
3. Generate a shared bearer token locally with
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
   Treat the printed value as a secret.
4. Enter the values in Render's secret prompts or the service's **Environment**
   page. Use a read-only Qdrant key scoped to the collection if available.

| Variable | Value |
|---|---|
| `LENDLENS_PUBLIC_DEMO` | `1`, set by Blueprint |
| `LENDLENS_GENERATION_PROVIDER` | `groq`, set by Blueprint |
| `GROQ_API_KEY` | Groq key for the existing configured model |
| `LENDLENS_QDRANT_URL` | HTTPS cluster endpoint containing `lendlens_core_dense_v1` |
| `LENDLENS_QDRANT_API_KEY` | Qdrant Cloud key |
| `LENDLENS_DEMO_TOKEN` | Shared bearer token generated above |

5. Deploy and copy the actual HTTPS service URL from the dashboard. Open its
   `/health` path and confirm HTTP 200 with `models_loaded: true`. Startup checks
   model initialization and Qdrant collection access. Groq generation is checked
   by an actual question in step 4.

## 3. Deploy Streamlit Community Cloud

1. Sign into [Streamlit Community Cloud](https://share.streamlit.io/) and authorize
   GitHub access to the repository.
2. Choose **Create app** and enter `datasriram/LendLens`, the reviewed branch, and
   main file path `streamlit_app.py`.
3. In **Advanced settings**, choose Python 3.14 and set the following root-level
   secrets, replacing the placeholders privately.

```toml
LENDLENS_PUBLIC_DEMO = "1"
LENDLENS_API_URL = "<actual HTTPS Render service base URL>"
LENDLENS_DEMO_TOKEN = "<same shared bearer token as Render>"
```

4. Deploy. In the app's sharing settings, allow public access and copy its actual
   HTTPS URL. Keep the backend provider keys in Render only.

[Streamlit deployment instructions](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)

## 4. Acceptance checks

1. Confirm the HTTPS backend `/health` endpoint returns 200 and
   `models_loaded: true`.
2. An unauthenticated POST to `/ask` with a valid question should return 401.
3. Open the Streamlit URL in a private browser window. Ask
   “What documents must an NBFC obtain when performing CDD for an individual?”
   Check for a substantive answer that includes Aadhaar and PAN. Open the
   supporting sources and check that displayed citation IDs have matching sources.
4. Ask “What is Tata Capital's CEO's favorite food?” Verify that the app abstains
   and displays no sources.
5. Check Render's memory metrics after cold startup and those requests. Open the
   Streamlit URL from a browser session without your hosting accounts signed in.

## Sizing, costs and limits

A local Windows process probe of the existing API imports, BGE and BM25 models,
and MiniLM reranking peaked at **948 MiB resident** and **1,432 MiB committed**
after 20 synthetic candidates. The probe excluded local Qdrant and Ollama.
Linux container usage can differ. Use one 2 GB Render worker initially and verify
observed memory on the deployed service. The 512 MB plans are too small for this
measured workload. Render lists 2 GB / 1 CPU at **US$25/month** for one instance.
Groq and Qdrant usage depend on your accounts. Startup can take longer when models
need to download. [Render pricing](https://render.com/pricing)

The demo allows one active generation and up to 12 admitted questions per minute
across all visitors. The in-process limit resets on restart and assumes the
configured single instance and worker. `/health` remains public.
