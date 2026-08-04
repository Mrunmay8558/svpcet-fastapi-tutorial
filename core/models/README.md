# `core/models/` — The Labels on the Boxes 🏷️

## The story

Every box in our fridge has a **label** printed on it that says exactly what must
be inside:

> 📦 **USER BOX**
> Must have: first name, last name, phone number, email, scrambled password
> May have: address, OTP code
> Filled in for you: role, status, created date, updated date

If you try to put in a box that's missing something, the label **refuses**. That
way we never end up with half-empty boxes confusing everyone later. 🚫

---

## The `User` label

```python
class User(Model):
    first_name: str
    last_name: str
    mobile_number: str
    user_role: UserRole = UserRole.CUSTOMER
    user_status: UserStatus = UserStatus.ACTIVE
    password: str
    otp: Optional[UserOTP] = None
    address: Optional[list[UserAddress]] = None
    email: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

### Three kinds of field 🔍

| Written like | Meaning | Example |
| --- | --- | --- |
| `name: str` | **Must** be filled in | `first_name` |
| `name: str = something` | Filled in for you if you don't | `user_role` |
| `name: Optional[X] = None` | Can be empty, that's fine | `address` |

### What is `Model`?

`User` inherits from `Model`, which comes from **ODMantic** (see
[`core/database/base_class.py`](../database/README.md)).

Inheriting from `Model` is what turns a plain Python class into a **MongoDB
collection**. ODMantic automatically:

- picks the collection name for you
- gives every document an `id`
- checks the label whenever you save

### Choosing the collection name yourself 🏷️

By default ODMantic names the collection after the class (`User` → `user`). This
model overrides that:

```python
model_config = {"collection": "users"}
```

So documents go into a collection called **`users`** (plural), which is the more
common convention.

> ⚠️ **Renaming a collection does not move existing data.** MongoDB doesn't
> rename anything for you — it just starts writing somewhere else. Documents
> saved before the change are still sitting in the old `user` collection, and
> queries will no longer find them. If you ever change this on a database that
> already has data, you have to migrate the documents across yourself. 🚚

You never write `db.user.insert_one({...})`. You write `User(...)` and save it. 🪄

---

## Enums: the only-these-words rule 🎨

```python
class UserRole(str, Enum):
    SUPERADMIN = "SUPERADMIN"
    CUSTOMER = "CUSTOMER"
```

An **enum** is a short list of allowed words. Like a box of 2 crayons — you may
pick either one, but you can't invent a new colour. 🖍️

Why is this so useful? Because plain strings rot:

```python
user_role = "custmer"      # 😱 typo. saved. nobody notices. forever.
user_role = "Customer"     # 😱 different capital letter = different value
user_role = "USER"         # 😱 word we never agreed on
```

With an enum, `UserRole.CUSTMER` crashes **immediately**, while you're writing
it. Loud and early beats silent and later. 📣

> 🐛 **A real bug here:** the old controller called
> `signJWT(user_role="USER", ...)` — but `"USER"` isn't in `UserRole` at all!
> The only options are `SUPERADMIN` and `CUSTOMER`. Because it was typed as a
> bare string, nothing complained, and wristbands went out with a role that
> doesn't exist. Now it uses `user.user_role.value`, straight from the enum. ✅

The `str` in `class UserRole(str, Enum)` is a small kindness: it means the enum
also behaves like normal text, so MongoDB and JSON can store it without fuss.

We have two enums:

| Enum | Choices | Means |
| --- | --- | --- |
| `UserRole` | `SUPERADMIN`, `CUSTOMER` | What are you allowed to do? |
| `UserStatus` | `ACTIVE`, `INACTIVE` | Is this account switched on? |

---

## Little labels inside the big label 🪆

Two helper shapes ride along inside `User`:

### `UserAddress`

```python
class UserAddress(BaseModel):
    address_line_1: str
    address_line_2: str
    state: str
    city: str
    pincode: str
```

And in `User` it's `Optional[list[UserAddress]]` — a **list**, because one person
can have a home address *and* an office address. 🏠🏢

### `UserOTP` — the one-time code

```python
class UserOTP(BaseModel):
    current_otp: str = Field(min_length=6, max_length=6)
    otp_expires_at: str
```

An **OTP** is a "One Time Password" — a 6-digit code we text or email you, that
works **once** and then dies. Like a secret handshake that only counts today. 🤝

This field is empty (`None`) for everyone right now, and **nothing in the project
uses it yet**. It's a slot reserved for any feature that needs to prove you
really control an email address or phone number — verifying a new email,
confirming a phone, or double-checking a risky action.

> 📌 Note that **change password does not need an OTP**. That flow proves it's
> you by asking for your *current password*, not by emailing a code — see the
> [login & change password flow guide](../apis/routes/LOGIN_AND_CHANGE_PASSWORD_FLOW.md).

`otp_expires_at` is what makes a code die. Without an expiry, a code emailed
today would still unlock the account next year. 😱

---

## Timestamps: who wrote the date? 🕐

```python
created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

That `default_factory` bit is sneaky-important. Compare:

```python
# ❌ WRONG — the time is frozen at the moment Python STARTED
created_at: datetime = datetime.now(timezone.utc)

# ✅ RIGHT — asks "what time is it?" fresh for every new user
created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

With the wrong version, every user you ever create gets **the exact same
birthday** — the moment the server booted. 🎂😬

`default_factory` means "don't give me a value, give me a little machine that
*makes* a value each time."

### Why `timezone.utc`? 🌍

**UTC** is one clock that the whole planet agrees on. Your users are in Nagpur,
your server might be in Singapore, your teammate is in London.

Store everything in UTC, and translate to local time only when you *show* it to a
human. Mix timezones in the database and you get bugs that only appear in
October. 🍂🐛

---

## The rule for this folder 📏

> Models describe **what data looks like when it's saved**. Nothing more.

✅ Field names, types, defaults, allowed values
❌ No saving, no fetching → that's the [storeroom keeper](../cruds/README.md)
❌ No business rules → that's the [chef](../controllers/README.md)

---

## ⚠️ The trap to remember

The **request form** ([schemas](../apis/schemas/README.md)) and the **box label**
(models) are *two different things*, and nothing keeps them in sync but you.

If the form accepts a field the label doesn't have, that field is **silently
thrown away** on save. That's exactly how `mobile_number` went missing. 🗑️

Whenever you add a field to a form, ask: *"does the label need it too?"* 🤔

---

## Where to go next

- 📦 [`../cruds/README.md`](../cruds/README.md) — who puts these boxes in the fridge
- 📥 [`../apis/schemas/requests/README.md`](../apis/schemas/requests/README.md) — the forms coming in
- 🚪 [`../database/README.md`](../database/README.md) — where `Model` comes from
