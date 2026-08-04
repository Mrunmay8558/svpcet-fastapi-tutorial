# `core/database/` — The Fridge Door 🚪

## The story

Our fridge is **MongoDB**. It's where everything is kept when the app is asleep.

But here's the thing about the fridge: **opening the door is slow.** 🐢

You have to find the handle, check you're allowed, wait for the light to come on…
If you did that fresh for every single order, the restaurant would grind to a
halt.

So we do something smarter: **we open the door once, at the very start, and leave
it open all day.** Everyone shares that one open door.

That's this whole folder.

---

## What's in here

| File | What it's for |
| --- | --- |
| `database.py` | Opens the fridge once and shares it with everyone |
| `base_class.py` | Names the label-maker that models use |

---

## `base_class.py` — the tiniest file in the project

```python
from odmantic import Model
Base = Model
```

Two lines! It just gives ODMantic's `Model` a nickname: `Base`.

**Why bother?** So that *one day*, if you switch to a different database
toolkit, you change this **one line** instead of hunting through every model
file. It's a little door you leave yourself for later. 🚪✨

---

## `database.py` — opening the door once

### The "there is only one" trick 🎩

```python
class _MongoClientSingleton:
    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super().__new__(cls)
            ...create the connection...
        return cls.instance
```

This is called the **Singleton pattern**, and it's easier than it sounds:

> "Do we already have one? Then take *that* one.
> No? Fine, make it — but only this once." 🔂

The `if not hasattr(cls, "instance")` line is the whole idea. The first caller
does the slow work of connecting. Every caller after that gets handed the same
connection instantly. ⚡

**What if we didn't do this?** Every request would open a brand-new connection to
MongoDB, and after a few hundred visitors the database would run out of room and
start refusing everyone. A very embarrassing way to fall over. 😵

### The two ways to get in

```python
def get_engine() -> AIOEngine:
    return _MongoClientSingleton().engine
```

**`get_engine()`** — the polite door. 🎩
Gives you the ODMantic engine, which speaks in *models*: `save(User(...))`,
`find_one(User, ...)`. This is what [`cruds/`](../cruds/README.md) uses, and it's
what you want 99% of the time.

```python
def MongoDatabase() -> core.AgnosticDatabase:
    return _MongoClientSingleton().mongo_client[DATABASE_NAME]
```

**`MongoDatabase()`** — the trapdoor. 🕳️
Gives you the raw Motor database, where you write MongoDB commands by hand. Only
needed for fancy things ODMantic can't express, like big aggregations. Powerful,
but no label-checking protects you here.

### Waking up and going to sleep 😴

```python
async def connect_to_mongo():    # at startup: open the door, check it works
async def close_mongo_connection():   # at shutdown: shut it politely
async def ping():                # "hello? are you there?" 📞
```

`ping()` is the app knocking on the fridge and waiting for a knock back. If
MongoDB is asleep or the password is wrong, you find out at **startup** with a
clear message — rather than at 2am when a customer tries to sign up. 🌙

> 📌 **A note for the curious:** these two functions are written and ready, but
> nothing calls them yet! FastAPI has a feature called `lifespan` for exactly
> this — running code at startup and shutdown. Wiring it up in
> [`core/apis/api.py`](../apis/README.md) is a nice next exercise. Right now the
> connection is created lazily, the first time somebody asks for the engine.

---

## Where the settings come from 🔑

```python
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "fastapi_tutorial")
```

`os.getenv("X", "fallback")` means: *"look for a setting called X. If it isn't
there, use this fallback instead."*

Those settings come from your `.env` file. Never from inside the code! Because:

- Your laptop's fridge and the real server's fridge are different fridges 🏠🏢
- Passwords must **never** be typed into a file that goes on GitHub 🔓

That's why the repo has a `.env.example` (a blank form, safe to share) while the
real `.env` is hidden by `.gitignore`. 🙈

### 🐛 The sneakiest bug in this whole project lived right here

Look at those two lines again. They run **the instant this file is imported** —
not later, not when you call a function. Immediately.

So if `.env` hasn't been loaded into the environment *yet*, `os.getenv` finds
nothing and quietly uses the fallbacks.

That's exactly what happened. `load_dotenv()` was being called inside
[`commons/auth.py`](../../commons/README.md), which Python imported **after**
this file. So:

- `.env` clearly said `DATABASE_NAME=SVPCET`
- The app cheerfully connected to `fastapi_tutorial` instead
- **No error. No warning.** Users were being saved to the wrong database
  entirely, and the only clue was one quiet log line. 🤫

**The fix:** `load_dotenv()` moved into [`core/__init__.py`](../README.md), which
Python *always* runs before anything else in `core/`.

**The lesson:** code at the top level of a file runs at *import time*, and import
order is real. When settings look ignored, ask "was the `.env` even loaded yet?"

---

## The rule for this folder 📏

> This folder knows **how to reach** the database. It knows nothing about users,
> orders, or any of your app's ideas.

✅ Connecting, sharing the connection, pinging, closing
❌ `find_one(User, ...)` → that's the [storeroom keeper's](../cruds/README.md) job

---

## Where to go next

- 📦 [`../cruds/README.md`](../cruds/README.md) — who actually uses the engine
- 🏷️ [`../models/README.md`](../models/README.md) — the labels ODMantic checks
- 🍽️ [`../README.md`](../README.md) — back to the restaurant overview
