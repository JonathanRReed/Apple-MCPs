# Apple-Tools E2E Checklist Template

Use this prompt with `Apple-Tools-MCP` for a safe self-test. Replace the bracketed placeholders before running it.

```text
Run an end-to-end Apple-Tools test using only my own accounts and my own contact record.

Rules:
- Do not contact anyone except me.
- Use Contacts first to confirm the target contact is me.
- If Contacts returns multiple matches for me, stop and ask once.
- If duplicate contacts are detected for me, stop and report that before sending.
- Use Mail only with my self-test email addresses.
- Use Messages only with my own contact methods.
- Create clearly labeled test items.
- Do not use shell, curl, UI scraping, or any external API when a native MCP supports the step.
- For Maps, use the native Apple Maps MCP only. If it is unavailable, mark the Maps step failed instead of substituting another provider.

Steps:
1. Send a test email from [YOUR_FROM_EMAIL] to [YOUR_TO_EMAIL].
2. Use Contacts to find [YOUR_SELF_CONTACT_NAME], verify it is me, then send a Messages test that says: "test!".
3. Create a reminder titled "Test reminder" due tonight in my default or specified general reminders list.
4. Ensure my dedicated digest folder exists in Notes, then read my calendar and mail context, then create a daily digest note and a weekly digest note in that folder.
5. Use Apple Maps to find restaurants near [YOUR_PLACE_ANCHOR], estimate drive time, and include the addresses in the digest note.
6. Use Apple System to read my current display appearance and text-size-related settings if available, then include that system context in the note.
7. Add my 5 most recent files to the note.

Use Apple-Tools for the full workflow. Return the ids or titles of the created note and reminder, confirm the exact self contact and self email that were used, and state whether each major step used a native MCP, a unified Apple-Tools wrapper, or a Shortcut bridge.
```
