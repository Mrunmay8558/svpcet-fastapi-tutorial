# `core/controllers/` — The Chef 👨‍🍳

## The story

The waiter brings the order into the kitchen and hands it to the **chef**.

The chef is the one who actually **thinks**:

- "Wait — we already made this exact dish for this person. I can't make another." 🙅
- "Before this goes in the fridge, I must scramble the password." 🔐
- "Now that it's saved, give them a wristband so they can come back in." 🎟️

All the **rules** of your app live here. Every "if this, then that" belongs to
the chef.

---

## The one job here: `register_user()`

Let's walk through it slowly, line by line.

### Step 1 — Has this person been here before?

```python
email = request.get("email")
user = await self.user_crud.get_by_email(email)
if user:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="User with this email already exists",
    )
```

The chef asks the storeroom keeper to look. If someone with that email is
already in the fridge, the chef **stops right there** and shouts an error.

**Why 400?** Status codes are little numbers that tell the customer *what kind*
of problem it was:

| Number | Meaning | Whose fault? |
| --- | --- | --- |
| `200` / `201` | All good! Created! | 🎉 nobody |
| `400` | "Your order doesn't make sense" | 🙋 yours |
| `401` | "I don't know who you are" | 🙋 yours |
| `404` | "That thing doesn't exist" | 🙋 yours |
| `422` | "Your form was filled in wrong" | 🙋 yours |
| `500` | "*We* broke. Sorry." | 🏠 ours |

`4xx` = you made a mistake. `5xx` = we made a mistake. Getting this right matters,
because apps calling your API make decisions based on that number.

### Step 2 — Hide the password 🔐

```python
password = request.get("password")
hashed_password = encrypt_password(password)
request["password"] = hashed_password
```

The real password gets swapped for a scramble **before** it goes anywhere near
the fridge. See [`commons/README.md`](../../commons/README.md) for how the
scrambling works.

> This is the single most important line in the whole app. If you skip it and
> your database ever leaks, you've handed away every user's real password — and
> people reuse passwords everywhere. 😰

### Step 3 — Save it 📦

```python
user = await self.user_crud.create_user(request)
```

The chef hands the finished dish to the storeroom keeper. The keeper hands back
the **saved** version — which now has an `id`, because MongoDB just made one.

### Step 4 — Give out a wristband 🎟️

```python
access_token = signJWT(
    user_role=user.user_role.value, id=str(user.id), expiry_duration=3600
)
```

`3600` seconds = **1 hour**. After that the wristband stops working and they must
log in again.

Why does a wristband expire at all? Because if someone steals it, you want the
damage to end quickly. A wristband that works forever is a key that can never be
taken back. 🔑😬

### Step 5 — Hand back a clean plate 🍽️

```python
return {
    "message": "User created successfully",
    "data": {
        "id": str(user.id),
        "first_name": user.first_name,
        ...
        "access_token": access_token,
    },
}
```

Look carefully at what is **missing** from that list: **the password.** 🔍

We build the reply by hand, naming each field we want to share. That way the
password hash *can't* sneak out, even by accident.

> 🐛 **This is a real bug we already fixed.** The old code did
> `result["access_token"] = access_token; return result` — it just handed back
> the *whole* box, password hash and all. Building the reply by hand is a bit
> more typing, and it's worth it every single time.

---

## Why `try` / `except` / `raise`?

```python
try:
    ...the whole recipe...
except Exception as error:
    logging.error(f"Error in UserController.register_user: {error}")
    raise
```

That last word `raise` is doing something subtle and important.

It means: **"write it in the diary, then throw the error onward anyway."** 📓➡️

If we *didn't* re-raise, the error would be quietly swallowed, the function would
return `None`, and the customer would get a cheerful "success!" for an order that
never happened. 👻

> **Rule:** log an error to explain it. Re-raise it so it still counts.
> Catching an error and staying silent is how ghosts get into your app.

---

## Why is everything `async` and `await`? ⏳

Talking to a database is **slow** — like waiting for a kettle to boil.

- **Without `async`:** the chef stands frozen staring at the kettle. 100 hungry
  customers wait behind them. 😤
- **With `async`:** the chef puts the kettle on, starts someone else's order, and
  comes back when it whistles. 🫖✨

`await` is the chef saying *"this bit will take a moment — go do something useful
and wake me when it's done."*

**The rule:** if a function is `async`, you must `await` it. Forget the `await`
and you don't get the food — you get a *promise* of food, which is very hard to
eat. 🍽️❓

---

## The rule for this folder 📏

> Controllers hold the **rules**. They know nothing about the web.

✅ "Can this person do this?", "What order do these steps go in?", "Scramble that first"
❌ Reading HTTP headers, setting cookies, building JSON responses → that's the [waiter](../apis/routes/README.md)
❌ Writing MongoDB queries → that's the [storeroom keeper](../cruds/README.md)

**The test:** could you call this controller from a command-line script, with no
web server running at all? If yes, you got it right. 🎯

---

## Where to go next

- 🧑‍🍳 [`../apis/routes/README.md`](../apis/routes/README.md) — the waiter who calls the chef
- 📦 [`../cruds/README.md`](../cruds/README.md) — the storeroom keeper the chef calls
- 🔐 [`../../commons/README.md`](../../commons/README.md) — the scrambler and wristband maker
