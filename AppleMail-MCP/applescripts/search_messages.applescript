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
    return safeText
end sanitizeText

on matchesQuery(queryText, subjectText, senderText, bodyText)
    if queryText is "" then
        return true
    end if
    ignoring case
        if subjectText contains queryText then
            return true
        end if
        if senderText contains queryText then
            return true
        end if
        if bodyText contains queryText then
            return true
        end if
    end ignoring
    return false
end matchesQuery

on boolText(flagValue)
    if flagValue then
        return "true"
    end if
    return "false"
end boolText

on run argv
    set queryText to item 1 of argv
    set mailboxName to item 2 of argv
    set unreadOnlyText to item 3 of argv
    set limitValue to (item 4 of argv) as integer

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
            if mailboxName is "" then
                set targetMailboxes to every mailbox of theAccount
            else
                repeat with theMailbox in every mailbox of theAccount
                    if (name of theMailbox) is mailboxName then
                        set end of targetMailboxes to theMailbox
                    end if
                end repeat
            end if

            repeat with theMailbox in targetMailboxes
                set mailboxLabel to name of theMailbox
                repeat with theMessage in messages of theMailbox
                    set isRead to read status of theMessage
                    if unreadOnly is true and isRead is true then
                    else
                        set subjectText to my sanitizeText(subject of theMessage)
                        set senderText to my sanitizeText(sender of theMessage)
                        set bodyText to my sanitizeText(content of theMessage)
                        if my matchesQuery(queryText, subjectText, senderText, bodyText) then
                            set previewText to bodyText
                            if (count characters of previewText) > 240 then
                                set previewText to text 1 thru 240 of previewText
                            end if
                            set dateText to ""
                            try
                                set dateText to my sanitizeText((date received of theMessage) as string)
                            end try
                            set appleId to (id of theMessage) as text
                            set end of rows to my sanitizeText(accountName) & fieldSeparator & my sanitizeText(mailboxLabel) & fieldSeparator & my sanitizeText(appleId) & fieldSeparator & subjectText & fieldSeparator & senderText & fieldSeparator & dateText & fieldSeparator & my boolText(isRead) & fieldSeparator & previewText
                            if (count of rows) >= limitValue then
                                return my joinText(rows, recordSeparator)
                            end if
                        end if
                    end if
                end repeat
            end repeat
        end repeat
    end tell

    return my joinText(rows, recordSeparator)
end run
