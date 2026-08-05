# SVPCET FastAPI Codebase — Complete Documentation

Everything about this project in one file: how the server works, how a request
travels through it, how authentication and authorisation are done, and the full
reference for every endpoint.

---

## Table of contents

1. [What this project is](#1-what-this-project-is)
2. [Getting started](#2-getting-started)
3. [Project structure](#3-project-structure)
4. [How the FastAPI server works](#4-how-the-fastapi-server-works)
5. [The four layers](#5-the-four-layers)
6. [Authentication and authorisation](#6-authentication-and-authorisation)
7. [Soft delete vs hard delete](#7-soft-delete-vs-hard-delete)
8. [API reference — User](#8-api-reference--user)
9. [API reference — Order](#9-api-reference--order)
10. [Data models](#10-data-models)
11. [Status codes used in this project](#11-status-codes-used-in-this-project)
12. [Testing the API](#12-testing-the-api)
13. [Bugs that were fixed, and why they happened](#13-bugs-that-were-fixed-and-why-they-happened)
14. [Known limitations](#14-known-limitations)

---

## 1. What this project is

A teaching project showing how to structure a production-style FastAPI codebase:

- **Layered architecture** — router → controller → CRUD → model
- **Async MongoDB** via Motor + ODMantic
- **JWT authentication** with bcrypt password hashing
- **Role-based authorisation** — `CUSTOMER` and `SUPERADMIN`
- **Soft delete** with restore, plus an administrator-only hard delete

The domain is a small food-ordering system. Users sign up, log in, and place
orders. Administrators manage users and orders.

---

## 2. Getting started

### Prerequisites

- Python 3.11+
- A running MongoDB instance (local install or MongoDB Atlas)

### Install

```bash
cd fastapi_project

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
```

Then edit `.env`:

| Variable        | Description                                | Example                     |
| --------------- | ------------------------------------------ | --------------------------- |
| `MONGODB_URL`   | MongoDB connection string                  | `mongodb://localhost:27017` |
| `DATABASE_NAME` | Database this app reads and writes         | `SVPCET`                    |
| `secret`        | Key used to sign JWT access tokens         | *(long random string)*      |
| `algorithm`     | JWT signing algorithm                      | `HS256`                     |

Generate a strong JWT secret:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

> `.env` is git-ignored and must never be committed. Anyone holding `secret` can
> mint a valid token for any user, including an administrator.

### Run

```bash
python main.py
```

Or directly with uvicorn:

```bash
uvicorn core.apis.api:app --reload --port 8000
```

| URL                                     | What it is             |
| --------------------------------------- | ---------------------- |
| `http://localhost:8000/docs`            | Swagger UI             |
| `http://localhost:8000/documentation`   | ReDoc                  |
| `http://localhost:8000/health`          | Health check           |

### Creating the first administrator

Sign-up always creates a `CUSTOMER` — `UserSignInRequest` does not accept a
`user_role` field, so nobody can register themselves as an administrator. The
first one is promoted directly in the database:

```javascript
// mongosh
use SVPCET
db.users.updateOne(
  { email: "admin@example.com" },
  { $set: { user_role: "SUPERADMIN" } }
)
```

After that, an existing administrator can promote anyone else through
`PUT /v1/users/{user_id}`.

---

## 3. Project structure

```
fastapi_project/
├── main.py                          # Entry point — launches uvicorn
├── requirements.txt                 # Dependencies, each annotated
├── .env.example                     # Template for environment variables
├── DOCUMENTATION.md                 # This file
├── commons/
│   ├── auth.py                      # JWT signing/decoding, password hashing
│   └── logger.py                    # Shared logger factory (console + file)
└── core/
    ├── __init__.py                  # Loads .env before anything else
    ├── apis/
    │   ├── api.py                   # FastAPI app, middleware, CORS, OpenAPI
    │   ├── routes/
    │   │   ├── user_router.py       # HTTP layer — user endpoints
    │   │   └── order_router.py      # HTTP layer — order endpoints
    │   └── schemas/requests/
    │       ├── user_request.py      # Pydantic request models — user
    │       └── order_request.py     # Pydantic request models — order
    ├── controllers/
    │   ├── user_controller.py       # Business logic — user
    │   └── order_controller.py      # Business logic — order
    ├── cruds/
    │   ├── user_crud.py             # Database access — users collection
    │   └── order_crud.py            # Database access — orders collection
    ├── database/
    │   ├── database.py              # Mongo connection singleton + engine
    │   └── base_class.py            # Base alias for ODMantic Model
    └── models/
        ├── user_model.py            # ODMantic document — User
        └── order_model.py           # ODMantic document — Order
```

---

## 4. How the FastAPI server works

### Startup, step by step

1. `python main.py` calls `uvicorn.run("core.apis.api:app", ...)`.
2. Python imports the `core` package, which runs `core/__init__.py`.
   That calls `load_dotenv()` — **before** any other `core.*` module is
   imported. The ordering is load-bearing: `core/database/database.py` reads
   `MONGODB_URL` and `DATABASE_NAME` at import time. If `.env` had not been
   loaded by then, `os.getenv` would return nothing, the fallback defaults would
   apply, and the app would silently connect to the wrong database.
3. `core/apis/api.py` runs. It creates the `FastAPI` instance, registers
   middleware, applies the CORS policy, and includes both routers.
4. Uvicorn begins listening. No MongoDB connection is opened yet — Motor
   connects lazily on the first actual query.

### The life of one request

Take `POST /v1/orders` with a JSON body and a bearer token:

```
   HTTP request
        │
        ▼
┌──────────────────────┐
│ Uvicorn (ASGI)       │  parses raw HTTP into an ASGI scope
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ CORS middleware      │  is this origin allowed?
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Security headers     │  runs on the way OUT — adds X-Frame-Options etc.
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Routing              │  match POST /v1/orders → create_order()
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Dependencies         │  Depends(oauth2_scheme) pulls the bearer token
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ Validation           │  body → OrderCreateRequest.  Fails → 422, and the
└──────────┬───────────┘  route function never runs
           ▼
┌──────────────────────┐
│ ROUTER               │  decodeJWT(token) → authenticated_user_details
│ order_router.py      │  no valid token → 401
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ CONTROLLER           │  business rules: does the user exist? may they do
│ order_controller.py  │  this? → raises HTTPException on a "no"
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ CRUD                 │  builds and runs the MongoDB query
│ order_crud.py        │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ MODEL / MongoDB      │  ODMantic validates the document, then writes it
└──────────┬───────────┘
           ▼
      JSON response  ◄── travels back up, security headers added on the way out
```

The important rule: **each layer only talks to the one directly below it.** A
router never touches the database; a CRUD class never decides who is allowed to
do what.

### What `api.py` sets up

**Security headers** (added to every response, including error responses):

| Header                      | What it prevents                                          |
| --------------------------- | --------------------------------------------------------- |
| `X-Frame-Options: DENY`     | Clickjacking — a hostile page framing this site invisibly  |
| `X-Content-Type-Options`    | MIME sniffing — an upload being executed as script         |
| `Strict-Transport-Security` | Downgrade to plaintext HTTP                               |
| `Permissions-Policy`        | Silent access to geolocation and microphone               |
| `Cache-Control: no-store`   | Authenticated responses sitting in a shared proxy cache   |
| `Server: Custom Server`     | Version disclosure that tells an attacker what to try     |

**CORS** is currently open (`allow_origins=["*"]`) for local convenience.
Restrict it to real origins before deploying.

**OpenAPI** is generated once by `custom_openapi()` and cached on
`app.openapi_schema`, so `/docs` does not re-walk every route on each load.

---

## 5. The four layers

| Layer          | File                    | Owns                                 | Must never                                    |
| -------------- | ----------------------- | ------------------------------------ | --------------------------------------------- |
| **Router**     | `apis/routes/*.py`      | Paths, methods, status codes, tokens | Contain business rules or touch the database   |
| **Controller** | `controllers/*.py`      | Business rules, permissions          | Write MongoDB queries or read HTTP headers     |
| **CRUD**       | `cruds/*.py`            | Database queries                     | Enforce rules or raise `HTTPException`         |
| **Model**      | `models/*.py`           | Document shape and validation        | Contain logic                                  |

### Router

```python
@order_router.post("/v1/orders", status_code=status.HTTP_201_CREATED)
async def create_order(request: OrderCreateRequest, token: str = Depends(oauth2_scheme)):
    try:
        authenticated_user_details = decodeJWT(token)
        if not authenticated_user_details:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        result = await OrderController().create_order(
            request.model_dump(), authenticated_user_details
        )
        return result
    except HTTPException as httperror:
        logging.error(...)
        raise                       # deliberate failure — keep its status code
    except Exception as error:
        logging.error(...)          # full detail to the log
        raise HTTPException(500, detail="Something Went Wrong")   # generic to the client
```

Two `except` blocks, and the order matters. `HTTPException` is caught first and
re-raised **unchanged**, so a `404` stays a `404`. Everything else is logged in
full and returned as a bare `500` — a stack trace or a driver message in a
response body tells an attacker which library versions you run.

`request.model_dump()` converts the Pydantic object to a plain dict, so the
controller never depends on the web layer and stays callable from a test or a
script.

### Controller

Owns the rules, knows nothing about HTTP beyond raising `HTTPException`:

```python
async def create_order(self, request: dict, authenticated_user_details: dict) -> dict:
    try:
        user = await self.user_crud.get_by_id(authenticated_user_details["id"])
        if not user:
            raise HTTPException(404, detail="Authenticated user not found")
        payload = {"created_by": ObjectId(authenticated_user_details["id"]), **request}
        result = await self.order_crud.create(payload)
        return {"message": "Order created successfully", "data": {...}}
    except Exception as error:
        logging.error(...)
        raise                       # bare raise — preserves the HTTPException above
```

A bare `raise` re-raises whatever was caught, with its type and status code
intact. Writing `raise HTTPException(500, ...)` here instead would turn every
deliberate `403` and `404` in the class into "Something Went Wrong".

Responses are built **field by field** rather than by dumping the stored
document. That is what keeps the password hash out of the API.

### CRUD

The only place MongoDB queries are written:

```python
async def get_by_id(self, order_id: str, include_deleted: bool = False):
    queries = [Order.id == ObjectId(order_id)]
    if not include_deleted:
        queries.append(Order.is_deleted != True)
    return await self.engine.find_one(Order, *queries)
```

Returns `None` for "not found" — never raises `HTTPException`. Whether a missing
record is an error is the controller's decision, not the database's.

### Model

ODMantic documents. `Model` supplies the `id` primary key and validates every
document on write. `model_config = {"collection": "orders"}` pins the collection
name instead of letting ODMantic derive one from the class name.

---

## 6. Authentication and authorisation

Two different questions, answered in this order:

- **Authentication** — *who are you?* Handled in the **router** by `decodeJWT`.
- **Authorisation** — *are you allowed?* Handled in the **controller** by
  reading `user_role` out of the decoded token.

### How a token is issued

`POST /v1/users/signup` and `POST /v1/user/login` both call `signJWT`:

```python
payload = {
    "user_role": user.user_role.value,   # "CUSTOMER" or "SUPERADMIN"
    "id": str(user.id),                  # the user's MongoDB _id
    "expires": time.time() + 3600,       # one hour
}
return jwt.encode(payload, JWT_SECRET, algorithm="HS256")
```

The lifetime is one hour (`ACCESS_TOKEN_EXPIRY_SECONDS` in
`user_controller.py`). Short by design: an issued token cannot be revoked, so
expiry is the only thing bounding the damage a leaked one can do.

> **Note:** expiry is carried in a custom `expires` claim, not the standard
> `exp`. PyJWT validates `exp` automatically but ignores `expires`, so the
> deadline is enforced by hand inside `decodeJWT`. Any other consumer of these
> tokens must do the same.

### How a token is used

Every protected endpoint follows the same shape:

```python
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/user/login")

async def some_endpoint(token: str = Depends(oauth2_scheme)):
    authenticated_user_details = decodeJWT(token)
    if not authenticated_user_details:
        raise HTTPException(401, detail="Invalid or expired token")
    result = await SomeController().some_method(authenticated_user_details)
```

`decodeJWT` returns `None` for **every** failure — bad signature, malformed
string, wrong algorithm, expired token. Collapsing them all to one outcome is
deliberate: distinct error messages would tell an attacker which part of a
forged token to fix next.

`authenticated_user_details` is the decoded payload:

```json
{ "user_role": "CUSTOMER", "id": "6a71de70028a818898f20246", "expires": 1785935616.5 }
```

### How the role check works

The controller reads the role from that payload:

```python
def check_admin(self, authenticated_user_details: dict) -> None:
    if authenticated_user_details.get("user_role") != UserRole.SUPERADMIN.value:
        raise HTTPException(403, detail="This operation requires administrator privileges")
```

**The role is never read from the request body or a query parameter.** The
caller controls both and could simply set either to `SUPERADMIN`. It comes only
from a JWT whose signature has been verified against the server's secret.

Three patterns appear in this codebase:

**1. Administrator required** — the whole endpoint is closed to customers:

```python
self.check_admin(authenticated_user_details)      # 403 for anyone else
```

Used by: `GET /v1/users`, `PUT /v1/users/{id}`, `PATCH /v1/users/{id}/status`,
`POST /v1/orders/{id}/restore`, `DELETE /v1/orders/{id}/permanent`.

**2. Owner or administrator** — a customer may act on their own records:

```python
is_owner = str(order.created_by) == str(authenticated_user_details["id"])
is_admin = authenticated_user_details["user_role"] == UserRole.SUPERADMIN.value
if not is_owner and not is_admin:
    raise HTTPException(403, detail="You are not authorized to access this order")
```

Note `str()` on both sides. `order.created_by` is an `ObjectId` and the token's
`id` is a string; comparing them directly is always `False`, which locks the
real owner out of their own order.

Used by: `GET /v1/orders/{id}`, `PUT /v1/orders/{id}`, `DELETE /v1/orders/{id}`,
`GET /v1/users/{id}`.

**3. Role widens the result** — the endpoint is open to everyone, but an
administrator sees more:

```python
if is_admin:
    created_by = user_id            # may filter to any user, or see all
else:
    created_by = authenticated_user_details["id"]    # forced to self
    include_deleted = False
```

Used by: `GET /v1/orders`. A customer passing `?user_id=<someone else>` is
ignored, not rejected — their list stays scoped to themselves.

### 401 vs 403

| Code  | Means                                         | Retry with same credentials? |
| ----- | --------------------------------------------- | ---------------------------- |
| `401` | I do not know who you are                     | May succeed                  |
| `403` | I know exactly who you are, and the answer is no | Never succeeds            |

### Password handling

- Hashed with **bcrypt** via passlib before it ever reaches the database.
- Bcrypt is deliberately slow and salts each hash, so two users with the same
  password get different digests and brute-forcing a stolen dump stays expensive.
- `verify_password` compares in constant time, so response timing does not
  reveal how much of a guess was right.
- Login answers the same "Invalid email or password" for an unknown email and a
  wrong password. Distinguishing them would confirm which addresses are
  registered.
- The hash is never logged and never serialised into a response.

---

## 7. Soft delete vs hard delete

The single most useful idea in this codebase, and the reason both exist.

### The difference

| | **Soft delete** | **Hard delete** |
| --- | --- | --- |
| What happens | `is_deleted = True`, `deleted_at` stamped | Document removed from the collection |
| Mongo operation | `$set` — an ordinary update | `deleteOne` |
| Still on disk? | Yes | No |
| Reversible? | Yes, one field | Only by restoring a backup |
| Visible in the API? | No — every read filters it out | No — it does not exist |
| References to its id | Still resolve | Point at nothing |
| Endpoint here | `DELETE /v1/orders/{id}` | `DELETE /v1/orders/{id}/permanent` |
| Who may | Owner or administrator | Administrator only |

### How soft delete is implemented

Two fields on the model:

```python
is_deleted: bool = Field(default=False)
deleted_at: Optional[datetime] = Field(default=None)
```

Deleting is an ordinary update — there is no special "delete" operation:

```python
now = datetime.now(timezone.utc)
payload = {"is_deleted": True, "deleted_at": now, "updated_at": now}
result = await self.order_crud.update(order_id, payload)
```

And every read filters the flag out:

```python
queries.append(Order.is_deleted != True)
```

> **Why `!= True` and not `== False`?** Orders written before the field existed
> have no `is_deleted` key at all, and `{"is_deleted": False}` does not match a
> document where the key is missing — those older orders would silently vanish
> from every list. `$ne: True` matches "false" and "absent" alike.
>
> The alternative is a one-off backfill:
> ```javascript
> db.orders.update_many({is_deleted: {$exists: false}}, {$set: {is_deleted: false}})
> ```

### Why soft delete is usually the right default

1. **Mistakes are recoverable.** A customer deletes the wrong order; an
   administrator restores it with one call. The hard-delete equivalent is
   restoring last night's backup and reconciling everything written since.
2. **History stays intact.** A deleted order still counts towards last month's
   revenue. Erase the document and the figure silently changes.
3. **References keep resolving.** An invoice pointing at order `abc123` still
   finds it. After a hard delete it points at nothing, and every screen showing
   that invoice has to cope with a hole.
4. **It is auditable.** `deleted_at` records *when*. Add a `deleted_by` field
   and it records *who*.

### Why hard delete still exists

1. **Legal erasure.** "Delete my data" under GDPR and similar means the row
   actually goes, and a flag does not satisfy it.
2. **Reclaiming space.** Soft-deleted rows accumulate forever. A retention job
   hard-deletes what was soft-deleted over a year ago.
3. **Test and junk data** that should never have existed.

This is why it is administrator-only, on a separate `/permanent` path rather
than a `?permanent=true` flag. A destructive operation should not be one
mistyped query parameter away from a recoverable one.

### The full lifecycle

```
   POST /v1/orders                            order created, is_deleted = false
        │
        ▼
   DELETE /v1/orders/{id}                     is_deleted = true, deleted_at set
        │                                     ├─ GET /v1/orders/{id}     → 404
        │                                     ├─ GET /v1/orders          → not listed
        │                                     └─ still in MongoDB ───────── verifiable
        │
        ├──────► POST /v1/orders/{id}/restore     is_deleted = false  (admin)
        │            └─ visible again, exactly as before
        │
        └──────► DELETE /v1/orders/{id}/permanent  document erased    (admin)
                     └─ gone from disk; restore now answers 404
```

Users are never deleted at all — not even softly. `PATCH
/v1/users/{id}/status` sets `INACTIVE`, which blocks login while every order
referencing that user still resolves. That is the same idea applied to a
different collection.

---

## 8. API reference — User

Base URL: `http://localhost:8000`

| Method  | Path                          | Auth          | Purpose                       |
| ------- | ----------------------------- | ------------- | ----------------------------- |
| `POST`  | `/v1/users/signup`            | None          | Register and receive a token  |
| `POST`  | `/v1/user/login`              | None          | Authenticate, receive a token |
| `POST`  | `/v1/user/change-password`    | Any user      | Change own password           |
| `GET`   | `/v1/user/me`                 | Any user      | Own profile                   |
| `GET`   | `/v1/users`                   | **Admin**     | List all users                |
| `GET`   | `/v1/users/{user_id}`         | Admin or self | One user's details            |
| `PUT`   | `/v1/users/{user_id}`         | **Admin**     | Update a user's details       |
| `PATCH` | `/v1/users/{user_id}/status`  | **Admin**     | Activate / deactivate         |

---

### `POST /v1/users/signup`

Registers a new user, hashes the password with bcrypt, and returns a JWT so the
caller is authenticated immediately without a second login request.

**Request**

```json
{
  "first_name": "Test",
  "last_name": "User",
  "mobile_number": "9876543210",
  "password": "SecurePass123",
  "email": "testuser@example.com",
  "address": [
    {
      "address_line_1": "12 MG Road",
      "address_line_2": "Near Park",
      "state": "Maharashtra",
      "city": "Nagpur",
      "pincode": "440001"
    }
  ]
}
```

`address` is optional. `user_role` and `user_status` are **not accepted** —
accepting them would let a client register itself as `SUPERADMIN`.

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

**Errors**

| Status | When                                                            |
| ------ | --------------------------------------------------------------- |
| `400`  | Email already registered                                        |
| `422`  | Password < 8 chars, mobile number not exactly 10, field missing  |

**Try it**

```bash
curl -X POST http://localhost:8000/v1/users/signup \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Test","last_name":"User","mobile_number":"9876543210","password":"SecurePass123","email":"testuser@example.com"}'
```

---

### `POST /v1/user/login`

**Request**

```json
{ "email": "testuser@example.com", "password": "SecurePass123" }
```

**Response — `200 OK`**

```json
{
  "message": "Login successful",
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

**Errors**

| Status | When                                        |
| ------ | ------------------------------------------- |
| `404`  | No account with that email                  |
| `401`  | Wrong password                              |
| `403`  | Account is `INACTIVE`                       |
| `422`  | Password shorter than 8 characters          |

---

### `POST /v1/user/change-password`

Requires a bearer token **and** the current password.

**Request**

```json
{ "old_password": "SecurePass123", "new_password": "NewSecurePass1" }
```

**Response — `200 OK`**

```json
{ "message": "Password changed successfully" }
```

**Errors**

| Status | When                                  |
| ------ | ------------------------------------- |
| `401`  | Token invalid/expired, or old password wrong |
| `404`  | Token valid but the account no longer exists |

The user ID comes from the token, so a caller can only ever change their own
password. The current password is required even though a valid token is already
present — otherwise a token left on a shared machine would be enough to lock the
real owner out.

**Try it**

```bash
curl -X POST http://localhost:8000/v1/user/change-password \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"old_password":"SecurePass123","new_password":"NewSecurePass1"}'
```

---

### `GET /v1/user/me`

Returns the authenticated caller's own profile. Takes no ID, which is what makes
"me" impossible to point at anyone else.

**Response — `200 OK`**

```json
{
  "message": "Profile retrieved successfully",
  "data": {
    "id": "6a71de70028a818898f20246",
    "first_name": "Test",
    "last_name": "User",
    "email": "testuser@example.com",
    "mobile_number": "9876543210",
    "user_role": "CUSTOMER",
    "user_status": "ACTIVE",
    "address": [],
    "created_at": "2026-08-05T12:13:36.925000+00:00",
    "updated_at": "2026-08-05T12:13:36.925000+00:00"
  }
}
```

**Errors:** `401` invalid/expired token · `404` account no longer exists

---

### `GET /v1/users` — administrators only

**Query parameters**

| Name          | Type   | Default | Notes                            |
| ------------- | ------ | ------- | -------------------------------- |
| `user_status` | enum   | *(all)* | `ACTIVE` or `INACTIVE`           |
| `page`        | int    | `1`     | ≥ 1                              |
| `page_size`   | int    | `20`    | 1–100                            |

**Response — `200 OK`**

```json
{
  "message": "Users retrieved successfully",
  "data": [
    {
      "id": "6a71de70028a818898f20246",
      "first_name": "Test",
      "last_name": "User",
      "email": "testuser@example.com",
      "mobile_number": "9876543210",
      "user_role": "CUSTOMER",
      "user_status": "ACTIVE",
      "created_at": "2026-08-05T12:13:36.925000+00:00"
    }
  ],
  "pagination": { "page": 1, "page_size": 20, "total": 4, "total_pages": 1 }
}
```

**Errors:** `401` invalid/expired token · `403` not an administrator ·
`422` unknown `user_status`, `page` < 1, or `page_size` > 100

> `page_size` is capped at 100. Without a ceiling, `?page_size=1000000` would ask
> MongoDB for the entire collection and load it into memory — a denial of service
> that takes one line in a URL bar.

**Try it**

```bash
curl "http://localhost:8000/v1/users?user_status=ACTIVE&page=1&page_size=20" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

### `GET /v1/users/{user_id}` — administrator, or the account holder

**Response — `200 OK`** — same shape as `/v1/user/me`.

**Errors**

| Status | When                                                |
| ------ | --------------------------------------------------- |
| `401`  | Token invalid or expired                            |
| `403`  | A customer asking for someone else's record         |
| `404`  | No such user, or the ID is malformed                |

> A malformed ID and a valid-but-absent one both answer `404`. Both mean "no such
> user here", and answering `400` for one would confirm the ID format to a caller
> guessing at it.

---

### `PUT /v1/users/{user_id}` — administrators only

Partial update: send only the fields that should change.

**Request**

```json
{ "first_name": "Renamed", "user_status": "INACTIVE", "user_role": "SUPERADMIN" }
```

Accepted fields: `first_name`, `last_name`, `mobile_number`, `email`, `address`,
`user_role`, `user_status`.

`password` is **not** accepted — an administrator overwriting someone's
credentials would be an account takeover with no trace of who typed it. Password
changes go through `/v1/user/change-password`, which requires the current one.

**Response — `200 OK`**

```json
{
  "message": "User updated successfully",
  "data": {
    "id": "6a71de70028a818898f20246",
    "first_name": "Renamed",
    "last_name": "ByAdmin",
    "email": "testuser@example.com",
    "mobile_number": "9876543210",
    "user_role": "CUSTOMER",
    "user_status": "ACTIVE",
    "updated_at": "2026-08-05T12:13:39.912000+00:00"
  }
}
```

**Errors**

| Status | When                                                       |
| ------ | ---------------------------------------------------------- |
| `401`  | Token invalid or expired                                   |
| `403`  | Not an administrator                                       |
| `404`  | No such user                                               |
| `400`  | The new email already belongs to another account           |
| `422`  | `user_role` / `user_status` not one of the permitted values |

This is the **only** path by which an account can be promoted to `SUPERADMIN`,
and it is reachable only by an existing administrator.

---

### `PATCH /v1/users/{user_id}/status` — administrators only

Activate or deactivate an account. This is how a user is retired — there is no
`DELETE /v1/users/{id}`.

**Request**

```json
{ "user_status": "INACTIVE" }
```

**Response — `200 OK`**

```json
{
  "message": "User inactive successfully",
  "data": {
    "id": "6a71de70028a818898f20246",
    "email": "testuser@example.com",
    "user_status": "INACTIVE",
    "updated_at": "2026-08-05T12:13:40.024000+00:00"
  }
}
```

**Errors**

| Status | When                                                  |
| ------ | ----------------------------------------------------- |
| `401`  | Token invalid or expired                              |
| `403`  | Not an administrator                                  |
| `404`  | No such user                                          |
| `400`  | An administrator changing **their own** status        |
| `422`  | `user_status` not `ACTIVE` or `INACTIVE`              |

An administrator cannot deactivate themselves. With a single administrator that
is the difference between a mis-click and an application nobody can administer
again.

Once `INACTIVE`, `POST /v1/user/login` answers `403` for that account.

> **Timing caveat:** an access token issued *before* deactivation keeps working
> until it expires, because a JWT is verified by signature alone and is never
> checked against the database. Deactivation therefore takes effect within one
> token lifetime (one hour), not instantly. See
> [Known limitations](#14-known-limitations).

---

## 9. API reference — Order

All order endpoints require a bearer token.

| Method   | Path                             | Auth              | Purpose                    |
| -------- | -------------------------------- | ----------------- | -------------------------- |
| `POST`   | `/v1/orders`                     | Any user          | Create an order            |
| `GET`    | `/v1/orders`                     | Any user          | List orders                |
| `GET`    | `/v1/orders/{order_id}`          | Owner or admin    | One order                  |
| `PUT`    | `/v1/orders/{order_id}`          | Owner or admin    | Update an order            |
| `DELETE` | `/v1/orders/{order_id}`          | Owner or admin    | **Soft** delete            |
| `POST`   | `/v1/orders/{order_id}/restore`  | **Admin**         | Undo a soft delete         |
| `DELETE` | `/v1/orders/{order_id}/permanent`| **Admin**         | **Hard** delete            |

---

### `POST /v1/orders`

**Request**

```json
{ "food_item": "Paneer Tikka", "food_type": "VEG", "quantity": 2 }
```

`food_type` must be `VEG` or `NON_VEG`. `quantity` must be greater than 0.

**Response — `201 Created`**

```json
{
  "message": "Order created successfully",
  "data": {
    "id": "6a7328f4375097bf3e7bdccb",
    "created_by": "6a71de70028a818898f20246",
    "food_item": "Paneer Tikka",
    "food_type": "VEG",
    "quantity": 2,
    "status": "IN_PROGRESS",
    "created_at": "2026-08-05T12:13:40.383000+00:00",
    "updated_at": "2026-08-05T12:13:40.383000+00:00"
  }
}
```

**Errors:** `401` invalid/expired token · `404` token subject no longer exists ·
`422` bad `food_type`, `quantity` ≤ 0, or a missing field

`created_by` is taken from the verified token, never from the request body —
there is no path by which a caller can place an order in someone else's name.

**Try it**

```bash
curl -X POST http://localhost:8000/v1/orders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"food_item":"Paneer Tikka","food_type":"VEG","quantity":2}'
```

---

### `GET /v1/orders`

A **customer** sees only their own orders. An **administrator** sees everyone's.

**Query parameters**

| Name              | Type | Default | Notes                                       |
| ----------------- | ---- | ------- | ------------------------------------------- |
| `order_status`    | enum | *(all)* | `IN_PROGRESS`, `COMPLETED`, `CANCELLED`     |
| `user_id`         | str  | *(all)* | **Admin only.** Ignored for customers.      |
| `include_deleted` | bool | `false` | **Admin only.** Ignored for customers.      |
| `page`            | int  | `1`     | ≥ 1                                         |
| `page_size`       | int  | `20`    | 1–100                                       |

**Response — `200 OK`**

```json
{
  "message": "Orders retrieved successfully",
  "data": [
    {
      "id": "6a7328f4375097bf3e7bdccb",
      "created_by": "6a71de70028a818898f20246",
      "food_item": "Paneer Tikka",
      "food_type": "VEG",
      "quantity": 2,
      "status": "IN_PROGRESS",
      "is_deleted": false,
      "created_at": "2026-08-05T12:13:40.383000+00:00",
      "updated_at": "2026-08-05T12:13:40.383000+00:00"
    }
  ],
  "pagination": { "page": 1, "page_size": 20, "total": 1, "total_pages": 1 }
}
```

Sorted newest first. `skip`/`limit` paging is applied by MongoDB, not in Python —
fetching everything and slicing the list would pull the whole collection into
the process.

**Errors:** `401` invalid/expired token · `422` bad enum or out-of-range paging

> A customer passing `?user_id=<someone else>` is silently ignored — their list
> stays scoped to themselves. Honouring it for everyone would make reading
> another customer's entire order history a matter of editing the URL.

---

### `GET /v1/orders/{order_id}`

**Response — `200 OK`** — the same order object as the create response.

**Errors**

| Status | When                                              |
| ------ | ------------------------------------------------- |
| `401`  | Token invalid or expired                          |
| `403`  | The order belongs to another user                 |
| `404`  | No such order, malformed ID, or soft-deleted      |

---

### `PUT /v1/orders/{order_id}`

Partial update — send only what should change.

**Request**

```json
{ "quantity": 5 }
```

Accepted fields: `food_item`, `food_type`, `quantity`, `status`.
`created_by` is **not** accepted — allowing it would let a caller reassign their
order to someone else, bypassing every ownership check with an ordinary update.

**Response — `200 OK`** — the updated order.

**Errors**

| Status | When                                                            |
| ------ | --------------------------------------------------------------- |
| `401`  | Token invalid or expired                                        |
| `403`  | The order belongs to another user                               |
| `404`  | No such order, or it is soft-deleted                            |
| `409`  | Order is `COMPLETED` or `CANCELLED` and caller is not an admin  |
| `422`  | `quantity` ≤ 0, or a bad enum value                             |

A finished order is closed to customer edits — raising the quantity on a
completed order would change what was delivered after the fact and desynchronise
it from whatever was invoiced. Administrators are exempt, because correcting a
mis-recorded order is what the role is for.

**Try it**

```bash
curl -X PUT http://localhost:8000/v1/orders/$ORDER_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"quantity":5}'
```

---

### `DELETE /v1/orders/{order_id}` — soft delete

Flags the order. The document stays in MongoDB.

**Response — `200 OK`**

```json
{
  "message": "Order deleted successfully",
  "data": {
    "id": "6a7328f4375097bf3e7bdccb",
    "is_deleted": true,
    "deleted_at": "2026-08-05T12:13:40.864000+00:00"
  }
}
```

**Errors:** `401` invalid/expired token · `403` someone else's order ·
`404` no such order, **or it is already deleted**

Deleting twice is a `404`: the lookup excludes soft-deleted records, so the
second call cannot find it. That keeps the operation honest — the caller is told
the record is not there rather than being handed a success for a no-op.

> Answers `200` with a body rather than `204 No Content`, because the response
> carries `is_deleted` and `deleted_at` — which is what makes it visible that the
> record was *flagged* rather than erased. `204` forbids a body entirely.

---

### `POST /v1/orders/{order_id}/restore` — administrators only

**Response — `200 OK`** — the restored order, with `"is_deleted": false`.

**Errors**

| Status | When                                        |
| ------ | ------------------------------------------- |
| `401`  | Token invalid or expired                    |
| `403`  | Not an administrator                        |
| `404`  | No such order (including hard-deleted ones) |
| `409`  | The order is not deleted, so nothing to restore |

`POST` rather than `PUT`: this triggers an action on an existing resource rather
than replacing its representation, and the second call answers `409`.

---

### `DELETE /v1/orders/{order_id}/permanent` — administrators only

**Irreversible.** The document leaves the collection.

**Response — `200 OK`**

```json
{ "message": "Order permanently deleted", "data": { "id": "6a7328f4375097bf3e7bdccb" } }
```

Only the ID comes back — there is no longer a document to describe.

**Errors:** `401` invalid/expired token · `403` not an administrator ·
`404` no such order

Soft-deleted orders **are** reachable here, since purging already-deleted
records is the common case — a retention job erasing whatever was soft-deleted
over a year ago.

---

## 10. Data models

### `User` — collection `users`

| Field           | Type                   | Notes                                        |
| --------------- | ---------------------- | -------------------------------------------- |
| `id`            | `ObjectId`             | Assigned by MongoDB on first save            |
| `first_name`    | `str`                  |                                              |
| `last_name`     | `str`                  |                                              |
| `mobile_number` | `str`                  | Text, so leading zeros survive               |
| `email`         | `str`                  | Login identifier; uniqueness enforced in the controller |
| `password`      | `str`                  | **Bcrypt hash** — never plain text           |
| `user_role`     | `UserRole`             | `CUSTOMER` (default) or `SUPERADMIN`         |
| `user_status`   | `UserStatus`           | `ACTIVE` (default) or `INACTIVE`             |
| `otp`           | `UserOTP \| None`      | Reserved for verification flows              |
| `address`       | `list[UserAddress] \| None` | Embedded, not a separate collection     |
| `created_at`    | `datetime`             | Timezone-aware UTC                           |
| `updated_at`    | `datetime`             | Timezone-aware UTC                           |

### `Order` — collection `orders`

| Field        | Type                  | Notes                                            |
| ------------ | --------------------- | ------------------------------------------------ |
| `id`         | `ObjectId`            | Assigned by MongoDB on first save                |
| `created_by` | `ObjectId`            | The owner's user `_id`, **not** a string         |
| `food_item`  | `str`                 |                                                  |
| `food_type`  | `FoodType`            | `VEG` or `NON_VEG`                               |
| `quantity`   | `int`                 |                                                  |
| `status`     | `OrderStatus`         | `IN_PROGRESS` (default), `COMPLETED`, `CANCELLED`|
| `is_deleted` | `bool`                | Soft-delete flag, default `false`                |
| `deleted_at` | `datetime \| None`    | When it was soft-deleted                         |
| `created_at` | `datetime`            | Timezone-aware UTC                               |
| `updated_at` | `datetime`            | Timezone-aware UTC                               |

Both timestamps use `default_factory`, so the current time is evaluated **per
document**. A plain default would freeze every record's timestamp at the moment
the module was imported.

`created_by` is an `ObjectId` rather than a string so it matches the `_id` of
the referenced user document. A string would compare unequal to every stored ID
and quietly break every ownership check.

### Request schemas are separate from models — on purpose

A request carries a plain-text password and no ID; a stored document carries a
bcrypt hash and an ID. Sharing one class between the two roles is exactly how
password hashes end up in API responses.

The two must be kept in agreement by hand. A field accepted by a request schema
but absent from the model is silently discarded on save.

---

## 11. Status codes used in this project

| Code  | Meaning              | Raised when                                                      |
| ----- | -------------------- | ---------------------------------------------------------------- |
| `200` | OK                   | A successful read, update, or soft delete                        |
| `201` | Created              | Signup, order creation                                           |
| `400` | Bad Request          | Duplicate email; an admin changing their own status              |
| `401` | Unauthorized         | Missing/forged/expired token; wrong password                     |
| `403` | Forbidden            | Valid token, insufficient permission; inactive account at login  |
| `404` | Not Found            | No such record, or a malformed ID                                |
| `409` | Conflict             | Editing a finished order; restoring an order that is not deleted |
| `422` | Unprocessable Entity | Schema validation failed — raised by FastAPI before your code runs |
| `500` | Internal Server Error| Anything unexpected. Details go to the log, never to the client  |

---

## 12. Testing the API

### Swagger UI

Open `http://localhost:8000/docs`.

To call a protected endpoint, get a token from `POST /v1/user/login` first, then
click **Authorize** and paste it.

> Swagger's **Authorize** dialog posts a *form-encoded* username and password to
> `tokenUrl` (`/v1/user/login`), but that endpoint expects **JSON** and will
> answer `422`. Paste the token you already hold instead of typing credentials
> into that dialog. Adding a small form-based token endpoint would make the
> dialog work — a reasonable exercise.

### curl — a full walkthrough

```bash
BASE=http://localhost:8000

# 1. Register
curl -s -X POST $BASE/v1/users/signup \
  -H "Content-Type: application/json" \
  -d '{"first_name":"Test","last_name":"User","mobile_number":"9876543210",
       "password":"SecurePass123","email":"testuser@example.com"}'

# 2. Log in and capture the token
TOKEN=$(curl -s -X POST $BASE/v1/user/login \
  -H "Content-Type: application/json" \
  -d '{"email":"testuser@example.com","password":"SecurePass123"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")

# 3. Own profile
curl -s $BASE/v1/user/me -H "Authorization: Bearer $TOKEN"

# 4. Create an order
ORDER=$(curl -s -X POST $BASE/v1/orders \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"food_item":"Paneer Tikka","food_type":"VEG","quantity":2}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

# 5. List, read, update
curl -s "$BASE/v1/orders?page=1&page_size=20" -H "Authorization: Bearer $TOKEN"
curl -s $BASE/v1/orders/$ORDER -H "Authorization: Bearer $TOKEN"
curl -s -X PUT $BASE/v1/orders/$ORDER \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"quantity":5}'

# 6. Soft delete, then confirm it is hidden but still on disk
curl -s -X DELETE $BASE/v1/orders/$ORDER -H "Authorization: Bearer $TOKEN"
curl -s $BASE/v1/orders/$ORDER -H "Authorization: Bearer $TOKEN"   # 404

# In mongosh — the document is still there:
#   db.orders.findOne({_id: ObjectId("<ORDER>")})   →  is_deleted: true

# 7. Restore, then erase (admin token required)
curl -s -X POST   $BASE/v1/orders/$ORDER/restore   -H "Authorization: Bearer $ADMIN_TOKEN"
curl -s -X DELETE $BASE/v1/orders/$ORDER/permanent -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Reading the logs

`commons/logger.py` writes to the console **and** to `logs/debug.log`:

```
[pid=73936] - [2026-08-05 17:43:38,558] - [core.controllers.user_controller] - [ERROR] - [Error in UserController.login_user: 401: Invalid email or password]
```

The process ID matters once the app runs under several workers — interleaved
records from concurrent processes are otherwise impossible to separate.

Note that deliberate `4xx` outcomes are logged at ERROR level too. That is
noisy: a wrong password is a normal event, not an application fault. Logging
them at WARNING and reserving ERROR for `5xx` would make a real failure stand
out.

> **Never log** credentials, password hashes, tokens, or OTP codes. Logs get
> copied, forwarded to aggregators, and read by people who are not authorised to
> see that material.

---

## 13. Bugs that were fixed, and why they happened

Every one of these was in the code before, and every one is worth recognising on
sight.

### 1. A coroutine that was never awaited

```python
result = OrderController().create_order(...)        # WRONG
result = await OrderController().create_order(...)  # right
```

`create_order` is `async`. Calling it without `await` returns a *coroutine
object*, not a result. FastAPI cannot serialise it, so the endpoint answered
`500` — and the order was never written at all. Python emits only a
`RuntimeWarning: coroutine was never awaited`, which is easy to miss in a busy
log.

### 2. A string compared against an `ObjectId`

```python
await self.engine.find_one(Order, Order.id == order_id)              # WRONG
await self.engine.find_one(Order, Order.id == ObjectId(order_id))    # right
```

MongoDB stores `_id` as a 12-byte `ObjectId`, never as text. The first line
builds `{"_id": {"$eq": "6a7328f4..."}}` — perfectly valid, and it matches
nothing. **Nothing raises.** The query returns `None` and the endpoint reports
`404` for a record that plainly exists. The same bug was in `UserCRUD.get_by_id`,
where it made `change-password` fail for every user.

### 3. `ObjectId` compared against a string

```python
if not order.created_by == authenticated_user_details["id"]:                   # WRONG
if str(order.created_by) != str(authenticated_user_details["id"]):             # right
```

`created_by` is an `ObjectId`, the token's `id` is a string — the comparison is
*always* `False`, so the genuine owner was refused access to their own order.
The bug fails closed, which is the safe direction, but it makes the feature
useless.

### 4. `HTTPException` swallowed by a broad `except`

```python
except Exception as error:
    logging.error(...)
    raise HTTPException(500, detail="Something Went Wrong")   # WRONG — in a controller
```

`HTTPException` **is** an `Exception`, so this caught the deliberate `403` from
bug 3 above and replaced it with a `500`. Two bugs stacked: the wrong answer,
and no way to see why.

In a **controller**, use a bare `raise` — it re-raises the original with its
status code intact. In a **router**, catch `HTTPException` first and re-raise it,
then convert everything else to a generic `500`.

### 5. A method called with the wrong arguments

```python
payload = {"password": new_hashed_password, "updated_at": ...}
await self.user_crud.update(user)              # WRONG — signature is update(id, data)
await self.user_crud.update(user_id, payload)  # right
```

`payload` was built and then never used, while `update` was called with one
argument where it takes two. A `TypeError` surfaced as `500`; the password was
never changed.

### 6. `await` on something that is not awaitable

```python
user_collection = await self.engine.get_collection(User)   # WRONG
user_collection = self.engine.get_collection(User)         # right
```

`get_collection` is a plain function. It returns a handle without touching the
database, so awaiting it raises `TypeError: object AsyncIOMotorCollection can't
be used in 'await' expression`.

Rule of thumb: `await` what performs I/O. Getting a *handle* is not I/O; using
it is.

### 7. A field name that did not exist

```python
"food_items": result.food_items,   # WRONG — the model field is food_item
"food_item": result.food_item,     # right
```

An `AttributeError` at response-building time, after the order had already been
written. The request succeeded, the client saw a `500`.

### 8. A copy-pasted message

Login answered `"User created successfully"`. Harmless, and exactly the kind of
thing that survives for years because nobody reads their own success messages.

---

## 14. Known limitations

Deliberate simplifications. Each is a reasonable next exercise.

1. **A token cannot be revoked.** Deactivating a user, or demoting an
   administrator, does not take effect until their current token expires (one
   hour). A JWT is verified by signature alone and is never checked against the
   database — that is the trade-off of stateless auth: no round-trip per request,
   bounded staleness. Fixes: a shorter expiry, a `token_version` on the user
   document compared on each request, or a denylist of revoked token IDs.

2. **Email uniqueness is enforced in application code, not by the database.**
   Two simultaneous signups with the same address can both pass the check and
   both insert. A unique index is the real fix:
   `db.users.createIndex({email: 1}, {unique: true})`.

3. **No index on `orders.created_by`.** Every order list is a full collection
   scan. Fine with fifty orders, not with fifty thousand:
   `db.orders.createIndex({created_by: 1, created_at: -1})`.

4. **Deep paging is slow.** A large `skip` makes the server walk and discard
   every skipped document. Range-based paging on the sort key
   (`created_at < <last seen>`) lets an index seek straight to the page.

5. **`UserCRUD.update` and `OrderCRUD.update` write with `$set`,** which is
   correct, but they do not validate the incoming dict against the model. A
   caller passing a key the model has never heard of will have it written.
   Controllers are the only callers, and they build the dict from a validated
   schema — but the CRUD layer does not enforce that.

6. **CORS is wide open** (`allow_origins=["*"]`). Restrict it before deploying.

7. **`GET /set-cookie` is a demonstration endpoint.** Remove it — it serves no
   purpose in a deployment and needlessly widens the API surface.

8. **`connect_to_mongo()` is never wired up.** The connection is created lazily
   on first use, so a misconfigured database is discovered on a user's first
   request rather than at startup. Registering it through FastAPI's `lifespan`
   parameter is the intended next step.

9. **The log file grows without bound.** `commons/logger.py` appends forever. A
   deployed service would use `logging.handlers.RotatingFileHandler`.

10. **Deliberate `4xx` outcomes are logged at ERROR level,** which buries real
    faults among ordinary wrong passwords.
