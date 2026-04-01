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
    set targetMailboxName to item 4 of argv
    set targetAccountName to item 5 of argv

    set fieldSeparator to ASCII character 31
    set recordSeparator to ASCII character 30

    tell application "Mail"
        set sourceAccount to missing value
        repeat with theAccount in every account
            if (name of theAccount) is accountName then
                set sourceAccount to theAccount
                exit repeat
            end if
        end repeat
        if sourceAccount is missing value then
            error "ACCOUNT_NOT_FOUND"
        end if

        set sourceMailbox to missing value
        repeat with theMailbox in every mailbox of sourceAccount
            if (name of theMailbox) is mailboxName then
                set sourceMailbox to theMailbox
                exit repeat
            end if
        end repeat
        if sourceMailbox is missing value then
            error "MAILBOX_NOT_FOUND"
        end if

        set targetMessage to missing value
        repeat with theMessage in messages of sourceMailbox
            if ((id of theMessage) as text) is appleId then
                set targetMessage to theMessage
                exit repeat
            end if
        end repeat
        if targetMessage is missing value then
            error "MESSAGE_NOT_FOUND"
        end if

        -- Resolve the destination mailbox
        set destAccount to sourceAccount
        if targetAccountName is not "" then
            set destAccount to missing value
            repeat with theAccount in every account
                if (name of theAccount) is targetAccountName then
                    set destAccount to theAccount
                    exit repeat
                end if
            end repeat
            if destAccount is missing value then
                error "TARGET_ACCOUNT_NOT_FOUND"
            end if
        end if

        set destMailbox to missing value
        repeat with theMailbox in every mailbox of destAccount
            if (name of theMailbox) is targetMailboxName then
                set destMailbox to theMailbox
                exit repeat
            end if
        end repeat
        if destMailbox is missing value then
            error "TARGET_MAILBOX_NOT_FOUND"
        end if

        move targetMessage to destMailbox

        return my boolText(true) & fieldSeparator & targetMailboxName & recordSeparator
    end tell
end run
