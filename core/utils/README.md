# `core/utils/` — The Helpers 🧰

## The story

Sometimes the chef needs something done that isn't cooking:

- 📧 "Post this letter to the customer."
- 🎨 "Make the letter look pretty."
- 📄 "Turn this bill into a PDF."

Those jobs don't belong to the waiter, the chef, *or* the storeroom keeper. They
get their own little helper desk. That's this folder.

---

## 📭 This folder is empty right now — on purpose

Nothing here yet! But the project is already planning for it. Look at
[`requirements.txt`](../../requirements.txt) — this is already installed:

```
aiosmtplib==3.0.0
```

**SMTP** is the language computers use to send email. The `aio` part means it's
**async**, so sending a letter doesn't freeze the whole restaurant while the post
office thinks about it. 📮⏳

The comments in `requirements.txt` even name the files that are coming:

```
core/utils/email/email_helper.py
core/utils/email/email_template_generator.py
```

---

## What will live here

```
utils/
└── email/
    ├── email_helper.py             📤 actually sends the email
    └── email_template_generator.py 🎨 makes the email look nice
```

### Why two files instead of one?

Because they're **two different jobs**, and jobs that change for different
reasons should live apart:

| File | Job | Changes when... |
| --- | --- | --- |
| `email_template_generator.py` | Writes the words 📝 | ...a designer wants prettier emails |
| `email_helper.py` | Posts the letter 📮 | ...you switch email providers |

Squash them together, and a designer tweaking a colour is editing the same file
as your mail server password. 😬

### A sketch of what they'd look like

```python
# email_template_generator.py — just builds text, sends nothing
def password_changed_template(first_name: str) -> str:
    return f"""
        <h2>Hi {first_name},</h2>
        <p>Your password was just changed.</p>
        <p>If this wasn't you, contact us straight away.</p>
    """

# email_helper.py — just sends, writes nothing
async def send_email(to: str, subject: str, html_body: str) -> None:
    ...aiosmtplib does its thing...
```

Notice: the generator returns a **string** and never touches the internet. That
means you can test it instantly, with no mail server anywhere. 🧪⚡

---

## Who will use this first?

The **change password** feature. 🔐

When someone changes their password, you email them to say so. Not to ask
permission — the change already happened — but as an **alarm bell**. 🔔 If a
thief got in and changed the password, that email is the owner's only warning
that anything happened at all.

👉 The full plan is written out in the
[**login & change password flow guide**](../apis/routes/LOGIN_AND_CHANGE_PASSWORD_FLOW.md).

> 🚨 **Never put the password in that email** — not the old one, not the new one.
> Emails sit in inboxes forever and travel through servers you don't control.
> Say *that* it changed, never *what* it changed to.

---

## The rule for this folder 📏

> Helpers do **one specific outside-world job** — send email, make a PDF, resize
> a picture, call another company's API.

✅ "Send an email", "generate a QR code", "upload to cloud storage"
❌ "Scramble a password" → used everywhere, no topic → [`commons/`](../../commons/README.md)
❌ "Should we email this person?" → that's a **rule** → [`controllers/`](../controllers/README.md)

**The difference between `utils/` and `commons/`:** 🤔
`commons/` is for tools with **no topic** (a logger, a hasher — every app has
them). `utils/` is for helpers that do a **specific chunky job** for *this* app.

---

## Where to go next

- 👨‍🍳 [`../controllers/README.md`](../controllers/README.md) — the chef who'll call these helpers
- 🔐 [`../../commons/README.md`](../../commons/README.md) — the other toolbox, and how it differs
