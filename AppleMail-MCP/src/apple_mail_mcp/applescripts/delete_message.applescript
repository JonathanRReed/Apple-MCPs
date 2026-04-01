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

        delete targetMessage

        return my boolText(true) & recordSeparator
    end tell
end run
