# `core/apis/` — The Front of the Restaurant 🚪

## The story

This is the part of the restaurant that **customers can actually see**: the front
door, the sign outside, the security guard, and the waiters.

Everything behind this folder (the chef, the fridge) is hidden from the world.
Customers only ever talk to this part.

| Thing here | What it is |
| --- | --- |
| `api.py` | The **building itself** — the door, the sign, the guard |
| [`routes/`](routes/README.md) | The **waiters** — one per kind of order |
| [`schemas/`](schemas/README.md) | The **order forms** — what a valid order looks like |

---

## `api.py` — building the restaurant 🏗️

This one file sets up the whole building, step by step.

### 1. Put up the building

```python
app = FastAPI(
    title="SVPCET FastAPI Codebase Tutorial",
    version="0.1 - Beta",
    redoc_url="/documentation",
)
```

`app` is the restaurant. Everything else gets attached to it.

### 2. Hire the security guard 💂

```python
@app.middleware("http")
async def add_security_headers(request, call_next):
    ...
```

**Middleware** is a helper who stands at the door and touches **every single**
request and response — no exceptions.

Ours is a guard who stamps extra safety notes onto every plate before it leaves
the kitchen:

| Stamp | What it tells the browser |
| --- | --- |
| `X-Frame-Options: DENY` | "Don't let anyone hide my page inside their page." (Stops a trick where a bad site puts our real page invisibly on top of theirs so you click things you can't see.) |
| `X-Content-Type-Options: nosniff` | "If I say it's text, treat it as text. Don't guess." |
| `Strict-Transport-Security` | "Always use the locked road (https), never the open one." |
| `Cache-Control: no-store` | "Don't keep a copy of this lying around." |
| `Server: Custom Server` | "Don't tell strangers which server software we run." (Burglars love knowing which lock you use. 🔓) |

Notice the shape of the function:

```python
response = await call_next(request)   # 1. let the order go through first
response.headers[...] = ...           # 2. then stamp the answer on its way out
return response
```

The guard can do things **before** the order goes in, and **after** the food
comes out. Very handy.

### 3. Open the gate for other websites 🌍

```python
origins = ["*"]
app.add_middleware(CORSMiddleware, allow_origins=origins, ...)
```

Browsers have a safety rule: a website at `mysite.com` is **not** allowed to call
an API at `otherplace.com` unless that API says "yes, I allow it."

**CORS** is how the API says yes. `"*"` means *"I allow everybody"*.

> ⚠️ `"*"` is fine for learning, but it's a wide-open front door. On a real app
> you'd list only your own site, like `["https://mysite.com"]`.

### 4. Bring in the waiters

```python
app.include_router(user_router, tags=["User Management"])
```

This says: "all the user-related orders are handled by this waiter." The `tags`
part just groups them under a nice heading in the docs.

### 5. Two tiny always-there endpoints

| Endpoint | What it's for |
| --- | --- |
| `GET /` | Says hello. Proof the app is awake. |
| `GET /health` | Says `{"status": "healthy"}`. |

`/health` looks silly but it's very important in real life. Hosting services ping
it every few seconds, and if it ever stops answering, they restart the app
automatically. It's the app's pulse. 💓

### 6. Write the menu automatically 📖

```python
app.openapi = custom_openapi
```

Here's the best FastAPI magic: **you never write API documentation.** FastAPI
reads your routes and your schemas and writes the menu for you.

Start the server and visit:

| Address | What you get |
| --- | --- |
| http://localhost:8000/docs | Swagger — a menu with a **"Try it out"** button 🎮 |
| http://localhost:8000/documentation | ReDoc — a prettier menu for reading |

The `custom_openapi()` function just lets us change the title on the menu, and
saves the result so it isn't rebuilt on every visit.

---

## The rule for this folder 📏

> Everything here is about **talking to the outside world** — doors, forms,
> headers, status codes.
>
> The moment you find yourself writing a *rule* ("only allow this if...",
> "charge them twice if...") — stop. That belongs to the chef in
> [`core/controllers/`](../controllers/README.md).

---

## Where to go next

- 🧑‍🍳 [`routes/`](routes/README.md) — the waiters (**and** the login + change password flow guide!)
- 📋 [`schemas/`](schemas/README.md) — the order forms
- 🍽️ [`../README.md`](../README.md) — back to the restaurant overview
