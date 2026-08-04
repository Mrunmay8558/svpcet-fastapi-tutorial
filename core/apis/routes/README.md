# `core/apis/routes/` — The Waiter 🧑‍🍳

> 📖 **Looking for how login and change-password work?**
> It's all here: [**LOGIN_AND_CHANGE_PASSWORD_FLOW.md**](LOGIN_AND_CHANGE_PASSWORD_FLOW.md)

## The story

The waiter is the only person in the restaurant the customer ever meets. 👋

Their job is small and strict:

1. Take the order 📝
2. Glance at the form to check it's filled in properly 📋
3. Walk it to the chef 👨‍🍳
4. Bring back whatever the chef made 🍽️

The waiter **does not cook**. The waiter **does not open the fridge**. If you
ever catch a waiter cooking, something has gone wrong in your kitchen. 🚨

---

## What a route looks like

```python
@user_router.post("/v1/users/signup", status_code=status.HTTP_201_CREATED)
async def user_signup(request: UserSignInRequest):
    try:
        request = request.model_dump()
        result = await UserController().register_user(request)
        return result

    except HTTPException as httperror:
        logging.error(f"Error in /v1/users/signup: {httperror}")
        raise
    except Exception as error:
        logging.error(f"Error in /v1/users/signup: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )
```

Let's take it apart. 🔧

### The decorator: the sign on the table

```python
@user_router.post("/v1/users/signup", status_code=201)
```

| Piece | Meaning |
| --- | --- |
| `@user_router` | "I belong to the user waiter" |
| `.post` | "This is for **creating** things" |
| `"/v1/users/signup"` | The address customers knock on |
| `status_code=201` | "When it works, say **201 Created**" |

**Why `.post` and not `.get`?**

| Verb | Means | Example |
| --- | --- | --- |
| `GET` | "Show me something" 👀 | See your profile |
| `POST` | "Make something new" ➕ | Sign up |
| `PUT` / `PATCH` | "Change something" ✏️ | Update your address |
| `DELETE` | "Remove something" 🗑️ | Delete your account |

A `GET` should never change anything. Ever. Browsers and search engines
happily click `GET` links on their own — imagine if one of them said
"delete account". 😱

**Why `/v1/`?**

That's the **version number**, and it's a promise to everyone using your API:

> "I will never break `/v1/`. If I need to change how this works in a way that
> breaks things, I'll build `/v2/` and leave `/v1/` alone." 🤝

Without it, the day you improve your API you break every phone app that's
already out there in the world. 📱💥

### One line, three jobs

```python
async def user_signup(request: UserSignInRequest):
```

By naming that type, FastAPI silently does all of this for you:

1. ✅ Reads the incoming JSON
2. ✅ Checks it against the [form](../schemas/README.md), replying `422` if it's wrong
3. ✅ Writes the documentation at `/docs`

Three chores, zero lines of code. 🎁

### Handing over to the chef

```python
request = request.model_dump()
result = await UserController().register_user(request)
return result
```

Turn the form into a plain dictionary, give it to the chef, hand back whatever
comes out. **Three lines.** That's a healthy route — it's boring, and boring is
the goal. 😴✨

---

## The two `except` blocks 🎣

This bit confuses everyone at first, so let's go slowly. There are **two kinds of
problem**, and they need opposite treatment.

### 1. Problems we saw coming 🙋

```python
except HTTPException as httperror:
    logging.error(...)
    raise
```

`HTTPException` is the chef **deliberately** shouting something meaningful, like
*"that email is already taken — that's a 400."*

We just write it in the diary and `raise` it onward, unchanged. The customer
deserves the real message.

> 🐛 **This exact spot had a real bug.** The `raise` was missing! So the code
> caught the chef's "400 — email already taken", logged it, and then... just fell
> off the end of the function. Python returns `None` from a function that ends
> without returning, so FastAPI cheerfully sent back:
>
> ```
> HTTP 201 Created
> null
> ```
>
> A **success** code, with nothing in it, for an order that definitely failed. 👻
> The customer's app would think the signup worked!
>
> **The lesson:** `except` without `raise` (or without returning something
> sensible) makes errors *vanish*. Catch it, log it, then let it keep going.

### 2. Problems we did *not* see coming 💥

```python
except Exception as error:
    logging.error(f"Error in /v1/users/signup: {error}")
    raise HTTPException(500, detail="Something Went Wrong")
```

This catches genuine surprises — the fridge unplugged, a typo in our own code,
the internet melting.

Notice the split personality here, and it's on purpose:

- **The diary gets the whole truth:** `'dict' object has no attribute 'id'` 📓
- **The customer gets a shrug:** `"Something Went Wrong"` 🤷

**Why hide it?** Because detailed crash messages are a gift to burglars. They
reveal your file names, your library versions, sometimes even bits of your
database. Say little to strangers, write everything in the diary. 🔒

---

## The endpoint that exists today

| Method | Path | What it does | Answers |
| --- | --- | --- | --- |
| `POST` | `/v1/users/signup` | Make a new account | `201` ✅ · `400` email taken · `422` bad form · `500` we broke |

Try it yourself:

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

Or just open http://localhost:8000/docs and press **"Try it out"**. 🎮

---

## The rule for this folder 📏

> A route should be **boring**. Take order → call chef → return answer.

✅ Decorators, status codes, calling one controller, turning errors into replies
❌ `if user already exists` → a rule → [chef](../../controllers/README.md)
❌ `engine.find_one(...)` → the fridge → [storeroom keeper](../../cruds/README.md)
❌ `encrypt_password(...)` → a rule about *when* to scramble → chef

**The test:** if your route is more than ~10 lines, the waiter has probably
started cooking. 👀

---

## Where to go next

- 🔑 [**LOGIN_AND_CHANGE_PASSWORD_FLOW.md**](LOGIN_AND_CHANGE_PASSWORD_FLOW.md) — **step-by-step plan for the next two features**
- 👨‍🍳 [`../../controllers/README.md`](../../controllers/README.md) — the chef
- 📋 [`../schemas/README.md`](../schemas/README.md) — the forms
