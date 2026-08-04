# `core/cruds/` — The Storeroom Keeper 📦

## The story

The storeroom keeper has the simplest job in the whole restaurant, and they are
very proud of it:

> **"You tell me what to put in the fridge, I put it in the fridge.
> You tell me what to fetch, I fetch it. I do not ask questions."** 🙂

They don't decide recipes. They don't check if you're allowed. They just
**store** and **fetch**.

---

## What does "CRUD" mean? 🔤

It's four words that cover *everything* you can ever do to saved data:

| Letter | Word | In the fridge | In MongoDB |
| --- | --- | --- | --- |
| **C** | **C**reate | Put a new box in 📥 | `engine.save()` |
| **R** | **R**ead | Look at a box 👀 | `engine.find_one()` |
| **U** | **U**pdate | Change what's in a box ✏️ | `engine.save()` again |
| **D** | **D**elete | Throw a box away 🗑️ | `engine.delete()` |

That's it. Every app in the world is mostly just CRUD wearing a costume. 🎭

---

## What's in `user_crud.py`

### Getting the fridge door

```python
def __init__(self):
    self.engine: AIOEngine = get_engine()
```

When the keeper starts their shift, they grab the handle to the fridge door. They
don't *build* a new fridge — there is only one, and
[`core/database/`](../database/README.md) looks after it.

### `create_user()` — put a box in

```python
async def create_user(self, user: dict) -> User:
    logging.info("Creating a new user in the database")
    return await self.engine.save(User(**user))
```

Two small things doing a lot of work:

**`User(**user)`** — the `**` unpacks a dictionary into named arguments:

```python
user = {"first_name": "Test", "email": "a@b.com"}
User(**user)        # is the same as writing:
User(first_name="Test", email="a@b.com")
```

This is also the moment the **label gets checked**. If a required field is
missing, `User(...)` complains right here, *before* anything is saved.

**`return await self.engine.save(...)`** — we return what `save()` gives back,
not what we were handed.

> 🐛 **This was our very first bug, and it's a perfect one to learn from.**
>
> The old code was:
> ```python
> await self.engine.save(User(**user))
> return user          # ← returns the plain dict we came in with
> ```
> The save worked fine! The user really was written to MongoDB. But the function
> returned the *original dictionary*, which has no `id` — because the `id` is
> created by **MongoDB**, at save time, and only exists on the object `save()`
> hands back.
>
> So the chef then asked for `result.id` and Python said:
> `'dict' object has no attribute 'id'` → the whole request died with a **500**.
>
> **The lesson:** after you save something, use *the thing the database gave
> back*, not the thing you sent. The database adds stuff. 🎁

### `get_by_email()` — look for a box

```python
async def get_by_email(self, email: str):
    user = await self.engine.find_one(User, User.email == email)
    return user
```

Read `find_one(User, User.email == email)` as:

> "Look in the **User** boxes 📦, and find one where the **email** label matches."

If nothing matches, you get `None` back — which is Python's way of shrugging. 🤷
Notice that the keeper does **not** panic about `None`. Deciding whether "not
found" is bad news is the [chef's](../controllers/README.md) job, not theirs.

`User.email == email` looks like a normal comparison but it isn't — ODMantic is
being clever and turning it into a real MongoDB query. The nice part is that if
you typo `User.emial`, Python yells at you immediately. With handwritten
`{"emial": ...}` queries you'd just get silent wrong answers forever. 😌

---

## Why bother with this folder at all? 🤷

You *could* write database queries directly inside the chef's code. Here's why
you shouldn't:

1. **One place to fix things.** If "find a user by email" needs to change, you
   change it here, once — not in 14 scattered spots.
2. **The chef stays readable.** `get_by_email(email)` tells a story.
   `await engine.find_one(User, User.email == email)` tells a *database*.
3. **You could swap the fridge.** Move from MongoDB to PostgreSQL and *only this
   folder* changes. The chef never notices. 🔄
4. **Testing gets easy.** In tests you hand the chef a pretend keeper that
   returns fake data. No database needed. ⚡

---

## The rule for this folder 📏

> CRUD files **only** save and fetch. They never decide anything.

✅ `save`, `find_one`, `find`, `delete`, `count`
❌ "raise an error if the user already exists" → that's a **rule**, so it's the [chef's](../controllers/README.md)
❌ "scramble the password before saving" → also a rule, also the chef's
❌ "return a 404" → status codes are the [waiter's](../apis/routes/README.md) world

**The test:** if you see `HTTPException` or `if` inside a CRUD file, something has
wandered into the wrong room. 🚪

---

## Where to go next

- 👨‍🍳 [`../controllers/README.md`](../controllers/README.md) — the chef who gives the orders
- 🚪 [`../database/README.md`](../database/README.md) — where the fridge door comes from
- 🏷️ [`../models/README.md`](../models/README.md) — the labels on the boxes
