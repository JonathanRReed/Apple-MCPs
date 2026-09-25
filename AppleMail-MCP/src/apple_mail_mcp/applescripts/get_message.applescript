on joinText(theItems, separatorValue)
    if (count of theItems) is 0 then
        return ""
    end if
    set previousDelimiters to AppleScript's text item delimiters
    set AppleScript's text item delimiters to separatorValue
    set joinedText to theItems as text
    set AppleScript's text item delimiters to previousDelimiters
    return joinedText
end joinText

on replaceText(sourceText, findText, replacementText)
    set previousDelimiters to AppleScript's text item delimiters
    set AppleScript's text item delimiters to findText
    set textParts to text items of sourceText
    set AppleScript's text item delimiters to replacementText
    set outputText to textParts as text
    set AppleScript's text item delimiters to previousDelimiters
    return outputText
end replaceText

on sanitizeText(valueText)
    if valueText is missing value then
        return ""
    end if
    set safeText to valueText as text
    set safeText to my replaceText(safeText, return, "\\n")
    set safeText to my replaceText(safeText, linefeed, "\\n")
    set safeText to my replaceText(safeText, (ASCII character 31), " ")
    set safeText to my replaceText(safeText, (ASCII character 30), " ")
    set safeText to my replaceText(safeText, (ASCII character 29), " ")
    set safeText to my replaceText(safeText, (character id 8232), " ")
    set safeText to my replaceText(safeText, (character id 8233), " ")
    return safeText
end sanitizeText

on joinRecipientAddresses(recipientItems, separatorValue)
    set addresses to {}
    repeat with recipientItem in recipientItems
        try
            set end of addresses to my sanitizeText(address of recipientItem)
        end try
    end repeat
    return my joinText(addresses, separatorValue)
end joinRecipientAddresses

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

    set fieldSeparator to ASCII character 31
    set recordSeparator to ASCII character 30
    set listSeparator to ASCII character 29

    tell application "Mail"
        -- Resolve concrete Mail objects instead of retaining repeat-loop item
        -- references (issue #23). Refuse duplicate names rather than guessing.
        set sourceAccount to my requireSingleMatch((get every account whose name is accountName), "ACCOUNT_NOT_FOUND", "ACCOUNT_AMBIGUOUS")
        set sourceMailbox to my requireSingleMatch((get every mailbox of sourceAccount whose name is mailboxName), "MAILBOX_NOT_FOUND", "MAILBOX_AMBIGUOUS")

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

        set subjectText to ""
        try
            set subjectText to my sanitizeText(subject of targetMessage)
        end try

        set senderText to ""
        try
            set senderText to my sanitizeText(sender of targetMessage)
        end try

        set dateText to ""
        try
            set dateText to my sanitizeText((date received of targetMessage) as string)
        end try

        set toAddresses to ""
        try
            set toAddresses to my joinRecipientAddresses(to recipients of targetMessage, listSeparator)
        end try

        set ccAddresses to ""
        try
            set ccAddresses to my joinRecipientAddresses(cc recipients of targetMessage, listSeparator)
        end try

        set isRead to true
        try
            set isRead to read status of targetMessage
        end try

        set bodyText to ""
        try
            with timeout of 10 seconds
                set rawBody to content of targetMessage
                if rawBody is not missing value then
                    set bodyText to my sanitizeText(rawBody)
                    if (count characters of bodyText) > 50000 then
                        set bodyText to text 1 thru 50000 of bodyText
                    end if
                end if
            end timeout
        end try

        set attachmentNames to {}
        try
            repeat with theAttachment in mail attachments of targetMessage
                set end of attachmentNames to my sanitizeText(name of theAttachment)
            end repeat
        end try
        set attachmentText to my joinText(attachmentNames, listSeparator)

        set rowText to my sanitizeText(accountName) & fieldSeparator & my sanitizeText(mailboxName) & fieldSeparator & my sanitizeText(appleId) & fieldSeparator & subjectText & fieldSeparator & senderText & fieldSeparator & toAddresses & fieldSeparator & ccAddresses & fieldSeparator & dateText & fieldSeparator & my boolText(isRead) & fieldSeparator & bodyText & fieldSeparator & attachmentText
        return rowText & recordSeparator
    end tell
end run
