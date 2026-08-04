# `core/` — The Restaurant 🍽️

## The story

This folder is our whole **restaurant**. Everything that makes the app actually
*do* something lives in here.

A restaurant works because everyone has **one job** and nobody does someone
else's job. The waiter doesn't cook. The chef doesn't go shopping. The
storeroom keeper doesn't decide the recipe.

Our code works exactly the same way. Here is the whole team:

| Folder | Who they are | Their one job |
| --- | --- | --- |
| [`apis/routes/`](apis/routes/README.md) | 🧑‍🍳 The **waiter** | Take the order, bring the food back |
| [`apis/schemas/`](apis/schemas/README.md) | 📋 The **order form** | Make sure the order makes sense |
| [`controllers/`](controllers/README.md) | 👨‍🍳 The **chef** | Decide the rules and cook |
| [`cruds/`](cruds/README.md) | 📦 The **storeroom keeper** | Put things in the fridge, take things out |
| [`models/`](models/README.md) | 🏷️ The **labels on the boxes** | Say what shape each thing must be |
| [`database/`](database/README.md) | 🚪 The **fridge door** | Open the fridge once, keep it open |
| [`utils/`](utils/README.md) | 🧰 The **helpers** | Extra jobs like sending emails |

---

## How an order travels 🚶

When someone signs up, the request walks through the restaurant like this:

```
     🌍 Internet
        │
        ▼
  ┌─────────────┐
  │   ROUTES    │  "Hi! What would you like?"           👉 apis/routes/
  │  (waiter)   │
  └─────────────┘
        │  first checks the order form 📋 (apis/schemas/)
        ▼
  ┌─────────────┐
  │ CONTROLLER  │  "Let me check the rules and cook."   👉 controllers/
  │   (chef)    │  Is this email already taken?
  └─────────────┘  Scramble the password!
        │
        ▼
  ┌─────────────┐
  │    CRUD     │  "Putting it in the fridge."          👉 cruds/
  │ (storeroom) │
  └─────────────┘
        │  uses the label 🏷️ (models/) and the door 🚪 (database/)
        ▼
     🗄️ MongoDB
```

And then the answer walks back out the same way, in reverse. 🔁

---

## The golden rules 📏

These three rules are the whole point of this project. Break them and the code
turns into spaghetti. 🍝

1. **The waiter never opens the fridge.**
   Routes must never talk to the database. They only call a controller.

2. **The chef never talks to the customer.**
   Controllers don't build web responses. They just return plain data (or raise
   an error). The waiter turns it into a reply.

3. **The storeroom keeper never decides the recipe.**
   CRUD files only save and fetch. "Is this email already taken?" is a *rule*,
   so it belongs to the chef, not the storeroom.

**Why do we care?** Because one day you'll want to add a phone app, or a
scheduled job, or a test. Each of those needs the *chef's* rules but not the
*waiter*. If the rules are tangled into the waiter, you have to copy-paste them.
And copy-pasted rules always drift apart and start disagreeing. 😖

---

## The one file sitting right here

### `__init__.py`

```python
from dotenv import load_dotenv
load_dotenv()

from commons.logger import logger
```

This tiny file is the restaurant's **front door**, and Python runs it
automatically the *very first* time anybody writes `from core...` anything.

That makes it the perfect place to `load_dotenv()` — it reads the secrets out of
your `.env` file and puts them where the rest of the app can find them.

> ⚠️ **This ordering is not decoration — it's a real bug we already hit.**
> `database.py` reads `DATABASE_NAME` the moment it is imported. Before we moved
> `load_dotenv()` up here, the `.env` file was being loaded *too late*, so the
> app quietly connected to a database named `fastapi_tutorial` instead of the
> `SVPCET` one we asked for. No error message. Just the wrong fridge. 🙃

It also re-shares the `logger`, which is why every file in the project can write
the short and friendly `from core import logger`.

---

## Where to go next

Pick whichever room you're curious about — each one has its own guide:

- 🧑‍🍳 [`apis/`](apis/README.md) — the front of the restaurant
- 👨‍🍳 [`controllers/`](controllers/README.md) — the rules
- 📦 [`cruds/`](cruds/README.md) — the storeroom
- 🏷️ [`models/`](models/README.md) — the labels
- 🚪 [`database/`](database/README.md) — the fridge door
