# Per-Server E2E Checklist

Use these as safe launch checks for the standalone servers. Keep all outbound actions limited to your own accounts and your own contact record.

## Apple Mail

- call `mail_health`
- search with `mail_search_messages("*")` or a self-test query
- send one test email to your own inbox
- verify reply, forward, mark read or unread, move, and delete on a test message only

## Apple Calendar

- call `calendar_health`
- list calendars
- list events in a known date range
- create a clearly labeled test event
- update it
- delete it

## Apple Reminders

- call `reminders_health`
- list reminder lists
- create a clearly labeled test reminder
- update it
- complete or uncomplete it
- delete it

## Apple Messages

- call `messages_health`
- resolve yourself through Contacts first
- send a test message to yourself only
- if history is blocked, verify that the guide points to Full Disk Access

## Apple Contacts

- call `contacts_health`
- search for your own contact card
- get full contact details
- create a clearly labeled test contact
- update it
- delete it

## Apple Notes

- call `notes_health`
- list accounts and folders
- create a clearly labeled test note
- append text
- verify existing content is preserved
- delete the test note if the workflow expects cleanup

## Apple Shortcuts

- call `shortcuts_health`
- list shortcuts
- run a harmless shortcut only if you know its behavior
- if testing stdin input, use a disposable string

## Apple Files

- call `files_health`
- list allowed roots
- inspect a test directory
- read a text file in an allowed root
- confirm recent files work

## Apple System

- call `system_health`
- read frontmost app, clipboard, battery, and status
- only test write actions like notifications or clipboard updates if the environment is meant for that

## Apple Maps

- call `maps_health`
- search places near a known anchor
- estimate a route
- build a Maps link
