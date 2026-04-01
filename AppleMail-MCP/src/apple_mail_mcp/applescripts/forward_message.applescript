on splitText(sourceText, separatorValue)
    if sourceText is "" then
        return {}
    end if
    set previousDelimiters to AppleScript's text item delimiters
    set AppleScript's text item delimiters to separatorValue
    set textParts to text items of sourceText
    set AppleScript's text item delimiters to previousDelimiters
    return textParts
end splitText

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

on boolText(flagValue)
    if flagValue then
        return "true"
    end if
    return "false"
end boolText

on run argv
    set accountName to item 1 of argv
    set mailboxName to item 2 of argv
    set appleId to item 3 of argv
    set toRaw to item 4 of argv
    set forwardBody to item 5 of argv
    set senderRaw to item 6 of argv

    set listSeparator to ASCII character 29
    set fieldSeparator to ASCII character 31
    set recordSeparator to ASCII character 30
    set toList to my splitText(toRaw, listSeparator)

    tell application "Mail"
        set targetAccount to missing value
        repeat with theAccount in every account
            if (name of theAccount) is accountName then
                set targetAccount to theAccount
                exit repeat
            end if
        end repeat
        if targetAccount is missing value then
            error "ACCOUNT_NOT_FOUND"
        end if

        set targetMailbox to missing value
        repeat with theMailbox in every mailbox of targetAccount
            if (name of theMailbox) is mailboxName then
                set targetMailbox to theMailbox
                exit repeat
            end if
        end repeat
        if targetMailbox is missing value then
            error "MAILBOX_NOT_FOUND"
        end if

        set targetMessage to missing value
        repeat with theMessage in messages of targetMailbox
            if ((id of theMessage) as text) is appleId then
                set targetMessage to theMessage
                exit repeat
            end if
        end repeat
        if targetMessage is missing value then
            error "MESSAGE_NOT_FOUND"
        end if

        set forwardMessage to forward targetMessage with opening window

        if forwardBody is not "" then
            set content of forwardMessage to forwardBody & return & return & content of forwardMessage
        end if

        if senderRaw is not "" then
            set sender of forwardMessage to senderRaw
        end if

        tell forwardMessage
            repeat with addressText in toList
                if (addressText as text) is not "" then
                    make new to recipient at end of to recipients with properties {address:addressText as text}
                end if
            end repeat
        end tell

        send forwardMessage

        set subjectText to ""
        try
            set subjectText to my sanitizeText(subject of forwardMessage)
        end try

        return my boolText(true) & fieldSeparator & subjectText & recordSeparator
    end tell
end run
