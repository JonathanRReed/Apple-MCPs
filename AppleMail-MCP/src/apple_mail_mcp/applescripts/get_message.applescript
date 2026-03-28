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

on run argv
    set accountName to item 1 of argv
    set mailboxName to item 2 of argv
    set appleId to item 3 of argv

    set fieldSeparator to ASCII character 31
    set recordSeparator to ASCII character 30
    set listSeparator to ASCII character 29

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
