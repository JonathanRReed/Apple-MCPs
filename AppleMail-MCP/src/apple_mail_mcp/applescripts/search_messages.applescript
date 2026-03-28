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

on boolText(flagValue)
    if flagValue then
        return "true"
    end if
    return "false"
end boolText

on run argv
    set queryText to item 1 of argv
    set mailboxFilter to item 2 of argv
    set unreadOnlyText to item 3 of argv
    set limitValue to (item 4 of argv) as integer

    -- Treat "*" or "%" as match-all (no filter)
    if queryText is "*" or queryText is "%" then
        set queryText to ""
    end if

    set fieldSeparator to ASCII character 31
    set recordSeparator to ASCII character 30
    set rows to {}
    set unreadOnly to false
    if unreadOnlyText is "true" then
        set unreadOnly to true
    end if

    tell application "Mail"
        repeat with theAccount in every account
            set accountName to name of theAccount
            set targetMailboxes to {}

            if mailboxFilter is "" then
                repeat with theMailbox in every mailbox of theAccount
                    set mbName to name of theMailbox
                    if mbName is "INBOX" or mbName is "Inbox" then
                        set end of targetMailboxes to theMailbox
                    end if
                end repeat
            else
                repeat with theMailbox in every mailbox of theAccount
                    if (name of theMailbox) is mailboxFilter then
                        set end of targetMailboxes to theMailbox
                    end if
                end repeat
            end if

            repeat with theMailbox in targetMailboxes
                set mailboxLabel to name of theMailbox
                set matchedMessages to {}
                try
                    if unreadOnly then
                        if queryText is "" then
                            set matchedMessages to (every message of theMailbox whose read status is false)
                        else
                            set matchedMessages to (every message of theMailbox whose (subject contains queryText or sender contains queryText) and read status is false)
                        end if
                    else
                        if queryText is "" then
                            set matchedMessages to (every message of theMailbox)
                        else
                            set matchedMessages to (every message of theMailbox whose (subject contains queryText or sender contains queryText))
                        end if
                    end if
                end try

                repeat with theMessage in matchedMessages
                    if (count of rows) >= limitValue then exit repeat
                    set subjectText to ""
                    set senderText to ""
                    set dateText to ""
                    set appleId to ""
                    set isRead to true
                    try
                        set subjectText to my sanitizeText(subject of theMessage)
                    end try
                    try
                        set senderText to my sanitizeText(sender of theMessage)
                    end try
                    try
                        set dateText to my sanitizeText((date received of theMessage) as string)
                    end try
                    try
                        set appleId to (id of theMessage) as text
                    end try
                    try
                        set isRead to read status of theMessage
                    end try
                    -- Use subject as preview — never read body during search to prevent hangs
                    set previewText to subjectText
                    set end of rows to my sanitizeText(accountName) & fieldSeparator & my sanitizeText(mailboxLabel) & fieldSeparator & my sanitizeText(appleId) & fieldSeparator & subjectText & fieldSeparator & senderText & fieldSeparator & dateText & fieldSeparator & my boolText(isRead) & fieldSeparator & previewText
                end repeat

                if (count of rows) >= limitValue then exit repeat
            end repeat
            if (count of rows) >= limitValue then exit repeat
        end repeat
    end tell

    return my joinText(rows, recordSeparator)
end run
