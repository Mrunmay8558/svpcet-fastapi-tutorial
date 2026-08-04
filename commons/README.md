# `commons/` — The Shared Toolbox 🧰

## The story

Imagine our app is a **restaurant**. 🍽️

In every restaurant there is a small toolbox that **everybody** is allowed to
use — the can opener, the timer, the notepad. It does not belong to the chef or
to the waiter. It just sits there so anyone can grab it.

`commons/` is that toolbox.

Anything here can be used by **any** part of the app, and the tools here never
need to know who is using them.

---

## What is inside

### 🔐 `auth.py` — the lock-and-key maker

This file does two jobs.

**Job 1: Hiding passwords.**

When you tell us your password `SecurePass123`, we must **never** write that
down as-is. If a thief ever peeked at our notebook, they would see everyone's
real password.

So we scramble it into something like `$2b$12$WJeC0.0ebF9...`. This scrambling is
called **hashing**, and the magic is that it only works **one way**:

```
"SecurePass123"  ──scramble──▶  "$2b$12$WJeC0..."     ✅ easy
"$2b$12$WJeC0..." ──unscramble──▶  "SecurePass123"    ❌ impossible
```

So how do we check your password next time you log in? We scramble what you just
typed, and see if the two scrambles match. We never need the real password again!

| Function | What it does |
| --- | --- |
| `encrypt_password(password)` | Scrambles a password before we save it |
| `verify_password(plain, hashed)` | Checks if a typed password matches the scramble |

**Job 2: Making wristbands.**

When you enter a theme park, they give you a **wristband**. After that you don't
have to prove who you are at every ride — you just show the wristband.

A **JWT token** is that wristband. It's a long string like `eyJhbGciOiJIUzI1...`
that says "this is user #6a71de70, they are a CUSTOMER, and this band stops
working at 5 o'clock."

The important part: the wristband is **signed** with our secret stamp. If someone
tries to draw their own wristband saying "I am the ADMIN", the stamp won't match
and we'll know it's fake.

| Function | What it does |
| --- | --- |
| `signJWT(user_role, id, expiry_duration)` | Makes a new wristband |
| `decodeJWT(token)` | Reads a wristband and checks the stamp is real |

The secret stamp lives in the `.env` file as `secret`. **It never goes on
GitHub.** That's why `.env` is in `.gitignore` and only `.env.example` is shared.

---

### 📓 `logger.py` — the diary

Every time something happens in our restaurant, we write it in a diary:

```
[2026-08-04 18:11:46] - [user_router] - [INFO] - [Calling /v1/users/signup endpoint]
[2026-08-04 18:11:47] - [user_crud]   - [INFO] - [Creating a new user in the database]
[2026-08-04 18:11:47] - [controller]  - [ERROR] - ['dict' object has no attribute 'id']
```

Why bother? Because when something breaks, the diary tells us **exactly where**
it broke. Without it, we'd only know "something went wrong" — and that's a very
sad way to fix a bug.

The diary is written in two places at once:

- 🖥️ On your **screen**, so you see it while you work
- 📄 In **`logs/debug.log`**, so you can read it later

To use it in any file, write these two lines at the top:

```python
from core import logger
logging = logger(__name__)

logging.info("Something good happened")
logging.error("Something bad happened")
```

`__name__` is a Python freebie that means "the name of this file". That's how the
diary knows which room the message came from.

---

## The rule for this folder 📏

> If a tool is useful to **more than one** part of the app, and it doesn't care
> about users or orders or any specific topic — it belongs in `commons/`.

✅ A password scrambler, a diary, a date formatter
❌ "Find a user by email" — that's about *users*, so it goes in `core/cruds/`

---

## Where to go next

- [`../core/README.md`](../core/README.md) — the restaurant itself
- [`../README.md`](../README.md) — how to run the whole thing
