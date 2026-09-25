on boolText(flagValue)
    if flagValue then
        return "true"
    end if
    return "false"
end boolText

on parseMessageID(rawId)
    try
        set numericId to rawId as integer
    on error
        error "INVALID_MESSAGE_ID"
    end try
    -- Reject coercions such as 1.5 -> 2; never mutate a different message.
    if numericId < 0 or (numericId as text) is not rawId then
        error "INVALID_MESSAGE_ID"
    end if
    return numericId
end parseMessageID

on requireSingleMatch(matchedItems, missingCode, ambiguousCode)
    if (count of matchedItems) is 0 then error missingCode
    if (count of matchedItems) is not 1 then error ambiguousCode
    -- The caller supplies Mail's evaluated result, not a live every-item specifier.
    return contents of item 1 of matchedItems
end requireSingleMatch

on run argv
    set accountName to item 1 of argv
    set mailboxName to item 2 of argv
    set numericMessageId to my parseMessageID(item 3 of argv)
    set targetMailboxName to item 4 of argv
    set targetAccountName to item 5 of argv
    set fieldSeparator to ASCII character 31
    set recordSeparator to ASCII character 30

    tell application "Mail"
        -- Resolve concrete Mail objects instead of retaining repeat-loop item
        -- references (issue #23). Refuse duplicate names rather than guessing.
        set sourceAccount to my requireSingleMatch((get every account whose name is accountName), "ACCOUNT_NOT_FOUND", "ACCOUNT_AMBIGUOUS")
        set sourceMailbox to my requireSingleMatch((get every mailbox of sourceAccount whose name is mailboxName), "MAILBOX_NOT_FOUND", "MAILBOX_AMBIGUOUS")

        -- Resolve the destination before the message lookup. Do not carry a
        -- positional source reference through a second account/mailbox scan.
        set destAccount to sourceAccount
        if targetAccountName is not "" then
            set destAccount to my requireSingleMatch((get every account whose name is targetAccountName), "TARGET_ACCOUNT_NOT_FOUND", "TARGET_ACCOUNT_AMBIGUOUS")
        end if
        set destMailbox to my requireSingleMatch((get every mailbox of destAccount whose name is targetMailboxName), "TARGET_MAILBOX_NOT_FOUND", "TARGET_MAILBOX_AMBIGUOUS")

        -- Use the ID from search, scoped to its original account and mailbox.
        -- Mail's "message id" is a separate property; use a numeric-id filter.
        -- No global search or automatic mutation retry if the message has moved.
        try
            set targetMessage to (get first message of sourceMailbox whose id is numericMessageId)
        on error errorMessage number errorNumber
            if errorNumber is -1728 then error "MESSAGE_NOT_FOUND"
            error errorMessage number errorNumber
        end try
        if (id of targetMessage) is not numericMessageId then error "MESSAGE_ID_MISMATCH"

        move targetMessage to destMailbox
        return my boolText(true) & fieldSeparator & targetMailboxName & recordSeparator
    end tell
end run
