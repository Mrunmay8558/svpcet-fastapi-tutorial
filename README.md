# SVPCET FastAPI Codebase Tutorial

A teaching project that shows how to structure a production-style FastAPI
codebase: layered architecture (router → controller → CRUD → model), async
MongoDB via Motor + ODMantic, JWT authentication, and bcrypt password hashing.

## Project structure

```
fastapi_project/
├── main.py                     # Entry point — launches uvicorn
├── requirements.txt            # Dependencies, each annotated with its purpose
├── .env.example                # Template for local environment variables
├── commons/
│   ├── auth.py                 # JWT signing/decoding, password hashing
│   └── logger.py               # Shared logger factory (console + file)
└── core/
    ├── apis/
    │   ├── api.py              # FastAPI app, middleware, CORS, OpenAPI
    │   ├── routes/             # HTTP layer — request/response only
    │   └── schemas/requests/   # Pydantic request models
    ├── controllers/            # Business logic
    ├── cruds/                  # Database access
    ├── database/               # Mongo connection singleton + ODMantic engine
    └── models/                 # ODMantic documents
```

The layering rule: routes never touch the database, controllers never build HTTP
responses beyond raising `HTTPException`, and CRUD classes never contain business
rules.

## Getting started

### 1. Prerequisites

- Python 3.11+
- A running MongoDB instance (local install or MongoDB Atlas)

### 2. Install

```bash
git clone <this-repo-url>
cd fastapi_project

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
```

Then edit `.env`:

| Variable       | Description                                        |
| -------------- | -------------------------------------------------- |
| `MONGODB_URL`  | MongoDB connection string                          |
| `DATABASE_NAME`| Database this app reads and writes                 |
| `secret`       | Key used to sign JWT access tokens                 |
| `algorithm`    | JWT signing algorithm (`HS256`)                    |

Generate a strong JWT secret with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Run

```bash
python main.py
```

Or directly with uvicorn:

```bash
uvicorn core.apis.api:app --reload --port 8000
```

The API is then available at http://localhost:8000

| URL                            | What it is           |
| ------------------------------ | -------------------- |
| `http://localhost:8000/docs`   | Swagger UI           |
| `http://localhost:8000/documentation` | ReDoc         |
| `http://localhost:8000/health` | Health check         |

## API

### `POST /v1/users/signup`

Registers a new user, hashes the password with bcrypt, and returns a JWT access
token.

**Request**

```json
{
  "first_name": "Test",
  "last_name": "User",
  "mobile_number": "9876543210",
  "password": "SecurePass123",
  "email": "testuser@example.com"
}
```

**Response — `201 Created`**

```json
{
  "message": "User created successfully",
  "data": {
    "id": "6a71de70028a818898f20246",
    "first_name": "Test",
    "last_name": "User",
    "email": "testuser@example.com",
    "mobile_number": "9876543210",
    "user_role": "CUSTOMER",
    "user_status": "ACTIVE",
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

The password hash is never returned to the client.

**Error responses**

| Status | When                                       |
| ------ | ------------------------------------------ |
| `400`  | A user with that email already exists      |
| `422`  | Validation failed (password < 8 chars, mobile number not 10 digits, missing fields) |

**Try it**

```bash
curl -X POST http://localhost:8000/v1/users/signup \
  -H "Content-Type: application/json" \
  -d '{
        "first_name": "Test",
        "last_name": "User",
        "mobile_number": "9876543210",
        "password": "SecurePass123",
        "email": "testuser@example.com"
      }'
```

## Notes

- `.env` is git-ignored — only `.env.example` is committed. Never commit real
  secrets.
- `logs/` is git-ignored; `commons/logger.py` writes to `logs/debug.log` at runtime.
- CORS is currently open (`allow_origins=["*"]`) to keep local testing simple.
  Restrict this before deploying anywhere real.
