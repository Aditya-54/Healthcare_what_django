# AI Usage

I used AI (ChatGPT / Claude) during this project as a **discussion and learning tool** — to understand concepts, validate decisions, and think through edge cases before writing code. Code was written by me.

---

## What I used AI for

- Understanding Django's custom user model lifecycle and why it must be defined before the first migration
- Discussing the tradeoffs between different authentication approaches
- Studying how JWT access/refresh token lifecycles work in practice
- Understanding queryset-level vs object-level permission enforcement
- Thinking through edge cases in the patient-doctor mapping (race conditions, duplicate assignments)
- Writing and structuring documentation
- Understanding how `pg_hba.conf` auth methods differ between local socket and TCP connections

---

## Sample Discussions

---

**Me:** I need to let users log in with their email instead of username. Should I just override the default User model or use AbstractUser?

**AI:** Both work, but the right choice depends on timing. If you use `AbstractUser`, you keep all the built-in fields and just add email-login on top — less work. But if you want email to be the *only* identifier (no username field at all), you need `AbstractBaseUser` which gives you a blank slate. The critical thing either way: you have to set `AUTH_USER_MODEL` in settings before running your very first `migrate`. Django bakes the user model into the migration graph from the start — changing it afterwards is a painful process involving wiping migrations. What does your assignment actually require?

**Me:** Email as login, no username needed. So AbstractBaseUser then?

**AI:** Yes. You'll also need to write a custom `BaseUserManager` with `create_user` and `create_superuser`. Set `USERNAME_FIELD = "email"` and Django's auth system will use that for `authenticate()` calls automatically.

---

**Me:** For patient ownership — should I check permissions at the view level or filter the queryset?

**AI:** Queryset filtering is stronger. If you only do object-level checks, a user who guesses another user's patient ID gets a 403, which tells them "that ID exists but you can't access it." If you filter the queryset first — `Patient.objects.filter(created_by=request.user)` — then the same request gets a 404. The record is effectively invisible. For medical data, that's the better behaviour. The object-level check (`IsOwner`) is still worth having as a second layer, but the queryset filter is your primary defence.

---

**Me:** What's the safest way to prevent the same doctor being assigned to the same patient twice?

**AI:** Two layers. First, check in the serializer's `validate()` method and return a clean error message. Second, add a `UniqueConstraint(fields=["patient", "doctor"])` in the model's `Meta` — this creates an actual database constraint. The serializer check handles the normal case and gives a readable error. The database constraint is the final backstop: even if two requests slip past the serializer simultaneously, the database will reject one of them with an integrity error. Both layers together are what you want.

**Me:** So I should catch that integrity error too?

**AI:** Yes — wrap the `serializer.save()` call in a try/except and return a 400 instead of letting a 500 bubble up. The serializer check will catch 99% of cases; the except block handles the rare race condition.

---

**Me:** Should I use DRF generic views or plain APIView for everything?

**AI:** Use generics where they genuinely remove repetition — `ListCreateAPIView` and `RetrieveUpdateDestroyAPIView` handle the standard CRUD pattern cleanly and you just override `get_queryset` and `perform_create`. For the mapping endpoints though, you have non-standard routes: GET by patient ID, DELETE by mapping ID. Those don't map neatly to a generic, so plain `APIView` is more readable there. The rule of thumb: if a generic view fits in five lines, use it. If you're fighting it to make it work, use APIView.

---

**Me:** My tests are passing but they run against the main database. Is that a problem?

**AI:** Yes, potentially. Django's test runner creates a separate database (`test_<your_db_name>`) by default, so your actual data is safe. But if you're seeing your real data in tests, that means you're probably calling the API externally rather than using `APITestCase`. With `APITestCase`, Django wraps each test in a transaction that gets rolled back — so your main database stays clean. Check that your test class extends `APITestCase` from `rest_framework.test`, not `TestCase` from `unittest`.

---

**Me:** I want to test that the unique constraint actually works at the DB level, not just the serializer. How?

**AI:** Create the duplicate directly using the ORM in your test setup — `PatientDoctorMapping.objects.create(patient=..., doctor=...)` — and then hit the POST endpoint with the same pair. The serializer's `validate()` should catch it and return 400. To specifically test the DB constraint, you could bypass the serializer by calling `PatientDoctorMapping.objects.create()` twice for the same pair and assert that the second call raises `IntegrityError`. Both are worth having.

---

**Me:** For the README, what should I document as assumptions versus limitations?

**AI:** Assumptions are decisions you made intentionally that someone reading the code might question — "why are doctors shared across users?" You state the assumption and briefly explain why. Limitations are things the project genuinely doesn't have yet — no Docker, no HTTPS, single process — and you note what the fix would be. Mixing them together makes it harder to evaluate the project. Keep them in separate sections.

---

## Summary

AI helped me understand the "why" behind design decisions rather than just the "what." The conversations above reflect the kind of back-and-forth that shaped how I thought about ownership enforcement, token design, duplicate prevention, and test strategy before sitting down to write the actual code.
