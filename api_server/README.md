# Wanxiang Rime HTTP API

This directory contains a small FastAPI application that wraps librime so the
Wanxiang schema provided by this repository can be accessed through an HTTP
endpoint.

The server exposes two routes:

- `GET /health` – simple health probe that returns `{ "status": "ok" }`.
- `POST /convert` – accepts a JSON body such as `{ "pinyin": "woaini" }` and
  responds with `{ "text": "我爱你" }` after committing the first candidate that
  librime returns.

## Quick start

1. **Install librime** – make sure `libRimeCore.so` (Linux), `librime.dylib`
   (macOS) or the Windows DLL is installed on the host.  Set the `LIBRIME_PATH`
   environment variable if it is not available in the default dynamic loader
   search path.
2. **Install Python dependencies**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r api_server/requirements.txt
   ```

3. **Run the API server**

   ```bash
   export LIBRIME_PATH=/path/to/libRimeCore.so
   uvicorn api_server.main:app --reload --host 0.0.0.0 --port 9000
   ```

   The server automatically points librime to the repository root for shared
   data.  To customise directories or the schema ID, the following environment
   variables are recognised:

   - `RIME_SHARED_DIR` – location of Rime shared data (defaults to the
     repository root).
   - `RIME_USER_DIR` – user data directory used for persistent state (defaults
     to `custom/api_user` inside the repo).
   - `RIME_SCHEMA_ID` – schema ID to load (defaults to `wanxiang`).

4. **Send requests**

   ```bash
   curl -X POST http://localhost:9000/convert \
        -H "Content-Type: application/json" \
        -d '{"pinyin": "nihao"}'
   ```

   Response:

   ```json
   {"text": "你好"}
   ```

## Implementation notes

- The Python binding uses `ctypes` to interface with a handful of librime C
  functions.  It is intentionally small and does not aim to expose the full API.
- Concurrency is handled with a per-session lock to keep librime calls
  thread-safe.
- Only the top candidate is returned today.  Extending the service to include
  additional candidates would require populating more of the librime data
  structures (e.g. `RimeContext`).
