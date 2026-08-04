# `core/apis/schemas/` — The Order Forms 📋

## The story

Before the waiter walks your order to the kitchen, they glance at it:

- Did you write your name? ✍️
- Is your phone number actually 10 digits, or did you type 3? 📞
- Is your secret password at least 8 letters long? 🔒

If something is missing or silly, the waiter hands the form straight back to you
— **without ever bothering the chef**.

That's what schemas do. They are the shape of a good order.

---

## Why this is such a big deal 🛡️

Without schemas, you'd write sad code like this in every single route:

```python
if "email" not in request:
    return "email missing"
if "password" not in request:
    return "password missing"
if len(request["password"]) < 8:
    return "password too short"
# ...and 30 more lines of this 😩
```

With schemas, you write the *shape* once and **Pydantic** checks it for you,
automatically, on every request:

```python
async def user_signup(request: UserSignInRequest):   # ← that's it. done.
```

If the order is bad, FastAPI never even calls your function. It replies with a
**422** and a message explaining exactly what was wrong:

```json
{
  "detail": [{
    "loc": ["body", "password"],
    "msg": "String should have at least 8 characters"
  }]
}
```

Three gifts for the price of one:
1. ✅ Bad data is stopped at the door
2. ✅ The error message writes itself
3. ✅ The documentation at `/docs` writes itself too

---

## What lives here

```
schemas/
└── requests/        📥 what comes IN from the customer
    └── user_request.py
```

Notice it says **requests**, plural-ready. In a bigger project you'd also grow a
sibling:

```
└── responses/       📤 what goes OUT to the customer
```

**Why keep them separate?** Because what comes in and what goes out are *not the
same shape*, and pretending they are is how passwords leak.

| | Has `password`? | Has `id`? | Has `access_token`? |
| --- | --- | --- | --- |
| **Request** (coming in) | ✅ yes | ❌ no (doesn't exist yet!) | ❌ no |
| **Response** (going out) | 🚨 **NEVER** | ✅ yes | ✅ yes |

That "NEVER" is not a joke. Sending the password back — even the scrambled
version — is a real bug that real apps really ship. Separate shapes make it hard
to do by accident.

---

## The rule for this folder 📏

> A schema describes **what data looks like**. Nothing else.
>
> No database calls. No `if user already exists`. No sending emails. A schema is
> a shape, not a brain. 🧠❌

---

## Where to go next

- 📥 [`requests/`](requests/README.md) — the actual forms, field by field
- 🚪 [`../README.md`](../README.md) — the front of the restaurant
