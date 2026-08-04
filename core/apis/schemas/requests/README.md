# `core/apis/schemas/requests/` — Forms Coming IN 📥

## The story

This folder holds the **blank forms** we hand to customers. One form per kind of
order.

Right now there is one form: `user_request.py`.

---

## `UserSignInRequest` — the sign-up form

```python
class UserSignInRequest(BaseModel):
    first_name: str = Field(..., description="The user's first name.")
    last_name: str = Field(..., description="The user's last name.")
    mobile_number: str = Field(..., min_length=10, max_length=10)
    password: str = Field(..., min_length=8)
    email: str = Field(...)
    address: Optional[List[UserAddress]] = Field(None)
```

Let's read it like a picture book. 📖

### What do the two dots mean? `...`

```python
first_name: str = Field(..., description="...")
                        ↑
                   this thing
```

Those three dots are Python's `Ellipsis`, and in Pydantic they mean one word:

> **REQUIRED.** You must fill this in. No blanks allowed.

If a field can be left empty, you put the default value there instead — like
`Field(None)` on `address`.

### What does `Optional` mean?

```python
address: Optional[List[UserAddress]] = Field(None)
```

- `Optional[...]` = "you may leave this blank" 🤷
- `List[...]` = "this is a list — you can give me more than one"
- So together: *"zero, one, or many addresses. Your choice."*

### What do `min_length` and `max_length` do?

```python
mobile_number: str = Field(..., min_length=10, max_length=10)
```

Both are 10, so this means **exactly 10 characters**. Type 3 digits and you get
bounced with a `422` before the chef ever hears about you.

```python
password: str = Field(..., min_length=8)
```

At least 8 characters. `"short"` (5 letters) → rejected. 🚫

### Why is `mobile_number` a `str` and not an `int`? 🤔

Great question, and it's a classic trap!

Phone numbers **look** like numbers but they don't **behave** like numbers:

- You never add two phone numbers together ➕❌
- `0987654321` is a real phone number, but as an `int` Python eats the leading
  zero and gives you `987654321` — **the wrong number!** 😱

**Rule of thumb:** if you'd never do maths with it, it's text.
Phone numbers, PIN codes, ID numbers, house numbers → all `str`.

---

## A nested form inside a form 🪆

`address` isn't a plain string — it's a `UserAddress`, which is its own little
shape borrowed from [`core/models/user_model.py`](../../../models/README.md):

```python
class UserAddress(BaseModel):
    address_line_1: str
    address_line_2: str
    state: str
    city: str
    pincode: str
```

So a full sign-up order can look like this:

```json
{
  "first_name": "Test",
  "last_name": "User",
  "mobile_number": "9876543210",
  "password": "SecurePass123",
  "email": "testuser@example.com",
  "address": [{
    "address_line_1": "12 Main Street",
    "address_line_2": "Near the park",
    "state": "Maharashtra",
    "city": "Nagpur",
    "pincode": "440001"
  }]
}
```

Pydantic checks the *outer* form **and** every *inner* form. Forms all the way
down. 🪆

---

## Turning a form into a plain box 📦

In the route you'll see this line:

```python
request = request.model_dump()
```

`model_dump()` turns the fancy Pydantic object into an ordinary Python
dictionary — a plain box of keys and values.

Why? So the chef and the storeroom keeper don't have to care that the order
originally arrived as a web form. They just get a box. That keeps them reusable
by anything: a web request, a test, a background job, a script. 🔁

---

## 🐛 A real bug that lived right here

The form asked for `mobile_number`. The **label on the storage box**
([`User` model](../../../models/README.md)) did *not* have a `mobile_number` field.

So what happened? The customer carefully typed their phone number, the form
happily accepted it... and when it reached the fridge, the number was **silently
thrown in the bin**. 🗑️ No error. No warning. Just gone.

**The lesson:** the request form and the database model are two different things,
and it is *your* job to keep them agreeing with each other. Nobody warns you.

*(It's fixed now — `mobile_number` was added to the `User` model.)*

---

## Adding a new form

Say you want login. Add this to `user_request.py`:

```python
class UserLoginRequest(BaseModel):
    email: str = Field(..., description="The user's email address.")
    password: str = Field(..., description="The user's password.")
```

That's the whole job. Then the route just says `request: UserLoginRequest` and
validation + docs appear for free. ✨

See the full plan in the
[**login & change password flow guide**](../../routes/LOGIN_AND_CHANGE_PASSWORD_FLOW.md).

---

## Where to go next

- 📋 [`../README.md`](../README.md) — why schemas exist
- 🏷️ [`../../../models/README.md`](../../../models/README.md) — the box labels
