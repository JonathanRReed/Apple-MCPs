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
    set replyBody to item 4 of argv
    set replyAllFlag to item 5 of argv
    set senderRaw to item 6 of argv

    set fieldSeparator to ASCII character 31
    set recordSeparator to ASCII character 30

    set shouldReplyAll to false
    if replyAllFlag is "true" then
        set shouldReplyAll to true
    end if

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

        if shouldReplyAll then
            set replyMessage to reply targetMessage with opening window and reply to all
        else
            set replyMessage to reply targetMessage with opening window
        end if

        set content of replyMessage to replyBody & content of replyMessage

        if senderRaw is not "" then
            set sender of replyMessage to senderRaw
        end if

        send replyMessage

        set subjectText to ""
        try
            set subjectText to my sanitizeText(subject of replyMessage)
        end try

        return my boolText(true) & fieldSeparator & subjectText & fieldSeparator & my boolText(shouldReplyAll) & recordSeparator
    end tell
end run
