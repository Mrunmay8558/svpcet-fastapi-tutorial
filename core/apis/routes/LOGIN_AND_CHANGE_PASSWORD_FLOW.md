# 🔑 How Login and Change Password Work

**A step-by-step flow guide — explained like you're five, then built like a pro.**

> 📌 **Read this first:** signup is **already built**. Login and change password
> are **not built yet** — this document is the *plan* for them. Every code block
> below is a blueprint you can follow, layer by layer.

---

## 📑 What's in here

1. [The big idea: wristbands](#1-the-big-idea-wristbands-)
2. [Flow A — Sign Up (already built ✅)](#2-flow-a--sign-up-already-built-)
3. [Flow B — Login](#3-flow-b--login-)
4. [Showing your wristband: protected endpoints](#4-showing-your-wristband-protected-endpoints-)
5. [Flow C — Change Password](#5-flow-c--change-password-)
6. [All three flows side by side](#6-all-three-flows-side-by-side-)
7. [Build order checklist](#7-build-order-checklist-)
8. [Mistakes that bite everyone](#8-mistakes-that-bite-everyone-)

---

## 1. The big idea: wristbands 🎟️

Imagine a theme park. 🎢

- **Sign up** = buying your ticket for the very first time 🎫
- **Login** = coming back the next day and showing your ticket to get a fresh
  wristband 🎟️
- **Change password** = you're already inside wearing your wristband, and you
  want to pick a new secret word 🔐

Once you're wearing the wristband, you don't prove who you are at every single
ride. You just flash the band. 💪

That wristband is the **JWT token**. Everything below is about how you get one —
and how you use it.

---

## 2. Flow A — Sign Up (already built ✅)

Here's the flow that already works, so you can see the shape before we copy it.

```
👤 "Hi! I'm new here."
    │  POST /v1/users/signup
    │  { first_name, last_name, mobile_number, email, password }
    ▼
📋 SCHEMA        Is the form filled in right?
                 password ≥ 8? phone exactly 10?          ❌ → 422
    │ ✅
    ▼
🧑‍🍳 ROUTE        Turns the form into a plain box, calls the chef
    │
    ▼
👨‍🍳 CONTROLLER   1. Is this email already taken?          ❌ → 400
                 2. Scramble the password 🔐
                 3. Ask the storeroom to save it
                 4. Make a wristband 🎟️
    │
    ▼
📦 CRUD          engine.save(User(**user))
    │
    ▼
🗄️ MongoDB       user saved with a brand-new id
    │
    ▼
👤 "201 Created! Here's your wristband." 🎟️
```

**Why give a wristband right after signup?** So the new user is *instantly*
logged in. Making someone sign up and then immediately log in again is a small
rudeness that loses real customers. 🙂

---

## 3. Flow B — Login 🔐

### The five-year-old version

You come back to the park. You say your **name** and your **secret word**.

The guard doesn't have your secret word written down anywhere — remember,
[we only ever kept a scramble of it](../../../commons/README.md). So the guard
**scrambles what you just said** and checks whether the two scrambles look the
same.

Same scramble? It's really you. Here's your wristband. 🎟️

### The flow

```
👤 "It's me, I'm back!"
    │  POST /v1/users/login
    │  { email, password }
    ▼
📋 SCHEMA        UserLoginRequest — both fields present?   ❌ → 422
    │ ✅
    ▼
🧑‍🍳 ROUTE        model_dump() → call the chef
    │
    ▼
👨‍🍳 CONTROLLER
    │
    ├─ 1️⃣  Look up the user by email
    │      user = await crud.get_by_email(email)
    │      not found? ────────────────────────▶ ❌ 401 "Invalid email or password"
    │
    ├─ 2️⃣  Check the secret word
    │      verify_password(typed, user.password)
    │      no match? ─────────────────────────▶ ❌ 401 "Invalid email or password"
    │
    ├─ 3️⃣  Is the account switched on?
    │      user.user_status == ACTIVE?
    │      INACTIVE? ─────────────────────────▶ ❌ 403 "Account is inactive"
    │
    └─ 4️⃣  All good — make a wristband
           signJWT(user.user_role.value, str(user.id), 3600)
    │
    ▼
👤 "200 OK! Here's your wristband." 🎟️
```

### 🕵️ Why both errors say the exact same thing

Look at steps 1 and 2. One means *"nobody has that email"*, the other means
*"wrong password"*. **We deliberately give the identical message for both.**

Why? Imagine a burglar trying emails one by one:

| If we said... | The burglar learns... |
| --- | --- |
| ❌ "No user with that email" | this email is **not** registered |
| ❌ "Wrong password" | 🎯 **this email IS registered!** |

That second message just handed them a list of your real customers, which they
can then attack, phish, or sell. This trick is called **user enumeration**. 🔍

One vague message for both. Always. 🤐

### The code sketch

**1. The form** — in [`schemas/requests/user_request.py`](../schemas/requests/README.md):

```python
class UserLoginRequest(BaseModel):
    """
    Payload for ``POST /v1/users/login``.

    Attributes:
        email: Email address used as the login identifier.
        password: Plain-text password, checked against the stored bcrypt hash.
    """

    email: str = Field(..., description="The user's email address.")
    password: str = Field(..., description="The user's password.")
```

**2. The waiter** — in `user_router.py`:

```python
@user_router.post("/v1/users/login", status_code=status.HTTP_200_OK)
async def user_login(request: UserLoginRequest):
    """
    Authenticate a user and issue an access token.

    Args:
        request: Validated login payload.

    Returns:
        dict: ``{"message": str, "data": {...}}`` including ``access_token``.

    Raises:
        HTTPException:
            * ``401 Unauthorized`` — email unknown or password incorrect. Both
              cases return the same message so the response cannot be used to
              discover which email addresses are registered.
            * ``403 Forbidden`` — the account is inactive.
            * ``500 Internal Server Error`` — unexpected failure.
    """
    try:
        logging.info("Calling /v1/users/login endpoint")
        result = await UserController().login_user(request.model_dump())
        return result
    except HTTPException as httperror:
        logging.error(f"Error in /v1/users/login: {httperror}")
        raise
    except Exception as error:
        logging.error(f"Error in /v1/users/login: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )
```

> Note the status code is **200 OK**, not 201. Logging in doesn't *create*
> anything — you already exist. 201 is only for "I made a new thing."

**3. The chef** — in [`controllers/user_controller.py`](../../controllers/README.md):

```python
async def login_user(self, request: dict) -> dict:
    """
    Authenticate a user and issue an access token.

    Args:
        request: Validated login values containing ``email`` and ``password``.

    Returns:
        dict: ``{"message": str, "data": {...}}`` with the user's public fields
        and an ``access_token``.

    Raises:
        HTTPException: ``401`` if the credentials do not match any active
            account; ``403`` if the account is inactive.

    Security:
        A missing user and a wrong password produce an identical response, so
        the endpoint cannot be used to enumerate registered email addresses.
    """
    try:
        logging.info("Calling UserController.login_user function")

        user = await self.user_crud.get_by_email(request.get("email"))

        # One message for both cases — see the Security note above.
        if not user or not verify_password(request.get("password"), user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if user.user_status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive",
            )

        access_token = signJWT(
            user_role=user.user_role.value,
            id=str(user.id),
            expiry_duration=ACCESS_TOKEN_EXPIRY_SECONDS,
        )
        return {
            "message": "Login successful",
            "data": {
                "id": str(user.id),
                "first_name": user.first_name,
                "email": user.email,
                "user_role": user.user_role.value,
                "access_token": access_token,
            },
        }
    except Exception as error:
        logging.error(f"Error in UserController.login_user: {error}")
        raise
```

**4. The storeroom** — nothing new needed! `get_by_email()` already exists. ♻️

> 🧠 **401 vs 403 — the classic mix-up:**
> `401 Unauthorized` = *"I don't know who you are."* (bad password)
> `403 Forbidden` = *"I know exactly who you are, and you still can't."* (banned account)

---

## 4. Showing your wristband: protected endpoints 🎟️

Everything so far was **public** — you can't show a wristband before you have
one. Change password is different: you must **already be logged in**.

### How you show it

You put the token in a header on every request:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

The word `Bearer` means *"whoever bears (carries) this token gets in."* That's
also the scary part — a stolen token works for anyone holding it, which is
exactly why tokens expire after an hour. ⏰

### The doorman 💂

We need one small helper that runs **before** the route, checks the wristband,
and figures out who you are. In FastAPI that's a **dependency**.

Add this to [`commons/auth.py`](../../../commons/README.md):

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security_scheme = HTTPBearer()


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> str:
    """
    Resolve the caller's user id from the ``Authorization`` header.

    Declared as a dependency on protected routes, so the check runs before the
    route function is entered and no endpoint can forget to perform it.

    Args:
        credentials: Bearer credentials extracted by FastAPI. A missing or
            malformed header is rejected before this function runs.

    Returns:
        str: The ``id`` claim from the verified token.

    Raises:
        HTTPException: ``401 Unauthorized`` if the signature is invalid or the
            token has expired.

    Note:
        Also registers the scheme in the OpenAPI document, which is what puts
        the **Authorize** button in ``/docs``.
    """
    payload = decodeJWT(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return payload["id"]
```

Then a protected route just asks for it:

```python
@user_router.post("/v1/users/change-password")
async def change_password(
    request: ChangePasswordRequest,
    user_id: str = Depends(get_current_user_id),   # 👈 the doorman
):
    ...
```

**Why a dependency instead of checking inside each route?** Because a check you
have to remember to write is a check somebody will eventually forget. Declaring
it in the signature makes it impossible to skip. 🔒

> 🎁 **Bonus:** once this exists, `/docs` grows an **Authorize** 🔓 button.
> Paste your token in once and Swagger attaches it to every request.

---

## 5. Flow C — Change Password 🔐

### The five-year-old version

You're already inside the park, wearing your wristband. You want a new secret
word.

The guard asks for **two** things:

1. Your **old** secret word 🔑
2. Your **new** secret word ✨

Why ask for the old one when you're already wearing a wristband? 🤔

Because a wristband might not be on the right wrist! Maybe you left your phone
unlocked on a table for two minutes. Anyone who picks it up is "logged in". If
changing the password needed nothing but the wristband, that stranger could
lock you out of your own account **forever** in about four seconds. 😱

Asking for the old password proves it's **really you**, not just someone holding
your phone.

### The flow

```
👤  POST /v1/users/change-password
     │  Authorization: Bearer eyJhbGci...        🎟️
     │  { current_password, new_password }
     ▼
💂 DOORMAN (dependency)
     ├─ Is the wristband real and unexpired?     ❌ → 401
     └─ ✅ hands the route the user's id
     │
     ▼
📋 SCHEMA        new_password ≥ 8 characters?    ❌ → 422
     │ ✅
     ▼
🧑‍🍳 ROUTE        Passes user_id + payload to the chef
     │
     ▼
👨‍🍳 CONTROLLER
     │
     ├─ 1️⃣  Load the user by id
     │      not found? ────────────────────────▶ ❌ 404
     │
     ├─ 2️⃣  Does the CURRENT password match?
     │      verify_password(current, user.password)
     │      no? ────────────────────────────────▶ ❌ 401 "Current password is incorrect"
     │
     ├─ 3️⃣  Is the new one actually different?
     │      new == current? ────────────────────▶ ❌ 400 "New password must be different"
     │
     ├─ 4️⃣  🔐 Scramble the new password
     ├─ 5️⃣  ⏰ Refresh updated_at
     └─ 6️⃣  💾 Save
     │
     ▼
👤  200 OK — "Password changed successfully." 🎉
```

### The code sketch

**1. The form** — in [`schemas/requests/user_request.py`](../schemas/requests/README.md):

```python
class ChangePasswordRequest(BaseModel):
    """
    Payload for ``POST /v1/users/change-password``.

    Attributes:
        current_password: The caller's existing password, re-entered to confirm
            the request comes from the account owner and not merely from
            whoever is holding a valid token.
        new_password: Replacement password, minimum eight characters.
    """

    current_password: str = Field(..., description="The user's current password.")
    new_password: str = Field(
        ..., description="The new password.", min_length=8
    )
```

> ⚠️ Notice `min_length=8` is on `new_password` but **not** on
> `current_password`. The old one just has to *match* — if it were somehow
> shorter than today's rule, we still need the user to be able to prove it and
> move to a compliant one.

**2. The waiter** — in `user_router.py`:

```python
@user_router.post("/v1/users/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    request: ChangePasswordRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Replace the authenticated caller's password.

    Requires a valid bearer token. The caller's identity is taken from that
    token, never from the request body, so no caller can target another
    account.

    Args:
        request: Validated payload holding the current and new passwords.
        user_id: Caller's id, resolved from the token by the auth dependency.

    Returns:
        dict: ``{"message": str}`` confirming the change.

    Raises:
        HTTPException:
            * ``401 Unauthorized`` — token invalid/expired, or the current
              password is wrong.
            * ``400 Bad Request`` — the new password matches the current one.
            * ``404 Not Found`` — the token is valid but the account no longer
              exists.
            * ``500 Internal Server Error`` — unexpected failure.
    """
    try:
        logging.info("Calling /v1/users/change-password endpoint")
        result = await UserController().change_password(
            user_id=user_id, request=request.model_dump()
        )
        return result
    except HTTPException as httperror:
        logging.error(f"Error in /v1/users/change-password: {httperror}")
        raise
    except Exception as error:
        logging.error(f"Error in /v1/users/change-password: {error}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something Went Wrong",
        )
```

> 🔒 **The single most important line in this whole document:**
> ```python
> user_id: str = Depends(get_current_user_id)
> ```
> The id comes from the **token**, never from the request body. If you let the
> client send `{"user_id": "..."}`, then anyone could change **anyone else's**
> password just by typing a different id. This is such a common mistake that it
> has a name: **IDOR** — Insecure Direct Object Reference. 🚨

**3. The chef** — in [`controllers/user_controller.py`](../../controllers/README.md):

```python
async def change_password(self, user_id: str, request: dict) -> dict:
    """
    Replace an authenticated user's password.

    Args:
        user_id: Caller's id, taken from the verified access token.
        request: Validated payload with ``current_password`` and
            ``new_password``.

    Returns:
        dict: ``{"message": str}`` confirming the change.

    Raises:
        HTTPException: ``404`` if the account no longer exists; ``401`` if the
            current password does not match; ``400`` if the new password is the
            same as the current one.

    Security:
        Re-verifying the current password is what distinguishes the account
        owner from someone who merely obtained a valid token — from an unlocked
        device, for example. A token alone is not sufficient authority to
        replace a credential.
    """
    try:
        logging.info("Calling UserController.change_password function")

        user = await self.user_crud.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        if not verify_password(request.get("current_password"), user.password):
            logging.warning(f"Incorrect current password for user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect",
            )

        if verify_password(request.get("new_password"), user.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from the current password",
            )

        user.password = encrypt_password(request.get("new_password"))
        user.updated_at = datetime.now(timezone.utc)
        await self.user_crud.update_user(user)

        return {"message": "Password changed successfully"}
    except Exception as error:
        logging.error(f"Error in UserController.change_password: {error}")
        raise
```

> 💡 **Why check "is it different" with `verify_password`?**
> You can't compare the new password to the stored hash with `==` — the stored
> value is a *scramble*. `verify_password(new, user.password)` is the only way
> to ask "is this the same as what's already there?" 🔍

**4. New storeroom jobs** — in [`cruds/user_crud.py`](../../cruds/README.md):

```python
async def get_by_id(self, user_id: str) -> Optional[User]:
    """
    Fetch a single user by primary key.

    Args:
        user_id: MongoDB ``ObjectId`` rendered as a string, as carried in the
            access token.

    Returns:
        The matching :class:`User`, or ``None`` when no document matches.

    Raises:
        bson.errors.InvalidId: If ``user_id`` is not a valid ObjectId.
        pymongo.errors.PyMongoError: If the query fails at the database level.
    """
    try:
        logging.info("Executing UserCRUD.get_by_id function")
        return await self.engine.find_one(User, User.id == ObjectId(user_id))
    except Exception as error:
        logging.error(f"Error in UserCRUD.get_by_id: {error}")
        raise


async def update_user(self, user: User) -> User:
    """
    Persist changes to an existing user document.

    Args:
        user: A :class:`User` already carrying an ``id``, with its fields
            mutated by the caller.

    Returns:
        The saved :class:`User`.

    Raises:
        pymongo.errors.PyMongoError: If the write fails at the database level.

    Note:
        ``engine.save()`` performs an insert or an update depending on whether
        the document already carries an ``id``, so one method covers both.
    """
    try:
        logging.info("Updating an existing user in the database")
        return await self.engine.save(user)
    except Exception as error:
        logging.error(f"Error in UserCRUD.update_user: {error}")
        raise
```

### Try it with curl

```bash
# 1. Log in and keep the token
TOKEN=$(curl -s -X POST http://localhost:8000/v1/users/login \
  -H "Content-Type: application/json" \
  -d '{"email":"testuser@example.com","password":"SecurePass123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")

# 2. Change the password using it
curl -X POST http://localhost:8000/v1/users/change-password \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"current_password":"SecurePass123","new_password":"EvenBetterPass456"}'
```

---

## 6. All three flows side by side 🗺️

```
                      ┌──────────────────────────────────┐
                      │            👤 A person            │
                      └──────────────────────────────────┘
                          │              │              │
             brand new?   │    returning?│    logged in │already?
                          ▼              ▼              ▼
                 ┌────────────┐  ┌────────────┐  ┌──────────────────┐
                 │  SIGN UP   │  │   LOGIN    │  │ CHANGE PASSWORD  │
                 │ ✅ built   │  │ 📝 planned │  │   📝 planned     │
                 │  public    │  │   public   │  │  🎟️ needs token  │
                 └────────────┘  └────────────┘  └──────────────────┘
                          │              │              │
                          │              │              ├─ old password? 🔑
                          │              │              ├─ new password? ✨
                          │              │              └─ 200 OK ✅
                          ▼              ▼
                      ┌──────────────────────┐
                      │  🎟️ JWT access token  │
                      │   good for 1 hour     │
                      └──────────────────────┘
                                  │
                                  └──▶ used by every protected endpoint
```

### The endpoint table

| Method | Path | Needs a token? | Gives one back? | Status |
| --- | --- | --- | --- | --- |
| `POST` | `/v1/users/signup` | ❌ no | ✅ yes | **built** ✅ |
| `POST` | `/v1/users/login` | ❌ no | ✅ yes | planned 📝 |
| `POST` | `/v1/users/change-password` | 🎟️ **yes** | ❌ no | planned 📝 |

The first two are **public** — they have to be, since you can't show a wristband
before you have one. 🐣 The third is the first **protected** endpoint in the
project.

---

## 7. Build order checklist ✅

Build **one whole flow at a time**, testing as you go. Don't write both endpoints
and then start testing — you'll be debugging two things at once. 😵

### Login

- [ ] Add `UserLoginRequest` to `schemas/requests/user_request.py`
- [ ] Add `login_user()` to `controllers/user_controller.py`
- [ ] Add the `POST /v1/users/login` route
- [ ] 🧪 Right password → `200` + token
- [ ] 🧪 Wrong password → `401`
- [ ] 🧪 Unknown email → `401` **with the identical message**
- [ ] 🧪 Paste the token into [jwt.io](https://jwt.io) and read the payload

### Change password

- [ ] Add `get_current_user_id()` dependency to `commons/auth.py`
- [ ] Add `get_by_id()` and `update_user()` to `cruds/user_crud.py`
- [ ] Add `ChangePasswordRequest` schema
- [ ] Add `change_password()` to the controller
- [ ] Add the `POST /v1/users/change-password` route
- [ ] 🧪 Happy path → `200`, then log in with the **new** password ✅
- [ ] 🧪 Old password no longer works → `401`
- [ ] 🧪 No `Authorization` header → `403`
- [ ] 🧪 Garbage token → `401`
- [ ] 🧪 Wrong `current_password` → `401`
- [ ] 🧪 New password same as current → `400`
- [ ] 🧪 New password shorter than 8 → `422`

> ⏱️ **Testing expiry:** temporarily pass `expiry_duration=10` when signing, wait
> eleven seconds, and confirm the protected route answers `401`.

---

## 8. Mistakes that bite everyone 🐛

Every one of these has shipped to production somewhere, in a real app, made by
real developers. 😅

### 🔴 Taking the user id from the request body
The worst one on the list. If the endpoint accepts `{"user_id": "..."}`, anyone
can change anyone else's password. **Always** take identity from the verified
token. (This is IDOR — see the note in section 5. 🚨)

### 🔴 Not asking for the current password
Covered above: an unlocked phone becomes a permanent account takeover. A token
proves *someone is logged in*; the current password proves *it's the owner*.

### 🔴 Telling burglars which emails exist
Vague, identical messages on login. Always. 🤐

### 🔴 Letting the new password equal the old one
Users click through forms fast. Without the check, "change your password" can
quietly change nothing at all, and the user believes they're safe. 🙈

### 🔴 Logging the password
Never put a password — old or new, plain or hashed — into a log line. Logs get
copied, shipped to aggregators, and read by people who shouldn't see them. 📓🚫

### 🔴 No limit on guessing
`current_password` is a password field, so it deserves the same **rate limiting**
as login. Without it, a stolen token becomes an offline-speed password guesser. 🚦

### 🟡 Not invalidating other sessions
After a password change, tokens issued *before* the change still work until they
expire. If someone changed their password *because* they were compromised, the
attacker keeps access for up to an hour. Real systems store a
`password_changed_at` timestamp and reject any token issued before it. ⏰

### 🟡 Forgetting `updated_at`
`user.updated_at = datetime.now(timezone.utc)` is one line, and skipping it means
your audit trail quietly lies about when the account last changed. 🕐

---

## Where to go next

- 🧑‍🍳 [`README.md`](README.md) — how routes work
- 👨‍🍳 [`../../controllers/README.md`](../../controllers/README.md) — where the rules live
- 🔐 [`../../../commons/README.md`](../../../commons/README.md) — hashing and JWT, explained
- 📦 [`../../cruds/README.md`](../../cruds/README.md) — the storeroom keeper
