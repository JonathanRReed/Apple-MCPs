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
    set appleId to item 3 of argv
    set numericMessageId to my parseMessageID(appleId)
    set readFlag to item 4 of argv

    set fieldSeparator to ASCII character 31
    set recordSeparator to ASCII character 30

    set shouldBeRead to true
    if readFlag is "false" then
        set shouldBeRead to false
    end if

    tell application "Mail"
        -- Resolve concrete Mail objects and look the message up by id in one
        -- Apple event. Walking `id of` every message took minutes on a
        -- mailbox of a few thousand messages (issue #23 pattern, as in
        -- get_message.applescript).
        set sourceAccount to my requireSingleMatch((get every account whose name is accountName), "ACCOUNT_NOT_FOUND", "ACCOUNT_AMBIGUOUS")
        set sourceMailbox to my requireSingleMatch((get every mailbox of sourceAccount whose name is mailboxName), "MAILBOX_NOT_FOUND", "MAILBOX_AMBIGUOUS")
        try
            set targetMessage to (get first message of sourceMailbox whose id is numericMessageId)
        on error errorMessage number errorNumber
            if errorNumber is in {-1728, -1719} then error "MESSAGE_NOT_FOUND"
            error errorMessage number errorNumber
        end try
        if (id of targetMessage) is not numericMessageId then error "MESSAGE_ID_MISMATCH"

        set read status of targetMessage to shouldBeRead

        return my boolText(shouldBeRead) & recordSeparator
    end tell
end run
