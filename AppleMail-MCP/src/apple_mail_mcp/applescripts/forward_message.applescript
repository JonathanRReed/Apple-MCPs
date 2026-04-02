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

on resolveAccountBySender(senderRaw)
    if senderRaw is "" then
        return missing value
    end if
    tell application "Mail"
        repeat with theAccount in every account
            try
                if (name of theAccount as text) is senderRaw then
                    return theAccount
                end if
            end try
            try
                if (email addresses of theAccount) contains senderRaw then
                    return theAccount
                end if
            end try
        end repeat
    end tell
    error "ACCOUNT_NOT_FOUND"
end resolveAccountBySender

on primaryEmailForAccount(theAccount)
    tell application "Mail"
        try
            return item 1 of (email addresses of theAccount) as text
        end try
    end tell
    return ""
end primaryEmailForAccount

on selectSenderPopup(senderRaw, senderEmail)
    tell application "Mail" to activate
    delay 0.4
    tell application "System Events"
        tell process "Mail"
            set frontmost to true
            set composeWindow to front window
            repeat with popupRef in every pop up button of composeWindow
                click popupRef
                delay 0.2
                set matchingItem to missing value
                try
                    repeat with menuItemRef in every menu item of menu 1 of popupRef
                        set itemName to name of menuItemRef as text
                        if senderEmail is not "" and itemName contains senderEmail then
                            set matchingItem to menuItemRef
                            exit repeat
                        end if
                        if senderRaw is not "" and itemName contains senderRaw then
                            set matchingItem to menuItemRef
                            exit repeat
                        end if
                    end repeat
                end try
                if matchingItem is not missing value then
                    click matchingItem
                    delay 0.3
                    return value of popupRef as text
                end if
                key code 53
                delay 0.1
            end repeat
            error "ACCOUNT_MENU_ITEM_NOT_FOUND"
        end tell
    end tell
end selectSenderPopup

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

    set resolvedAccountLabel to ""
    set senderEmail to ""

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
            set matchedAccount to my resolveAccountBySender(senderRaw)
            set senderEmail to my primaryEmailForAccount(matchedAccount)
            set sender of forwardMessage to senderRaw
        end if

        tell forwardMessage
            repeat with addressText in toList
                if (addressText as text) is not "" then
                    make new to recipient at end of to recipients with properties {address:addressText as text}
                end if
            end repeat
        end tell
    end tell

    if senderRaw is not "" then
        set resolvedAccountLabel to my sanitizeText(my selectSenderPopup(senderRaw, senderEmail))
    end if

    tell application "Mail"
        send forwardMessage

        set subjectText to ""
        try
            set subjectText to my sanitizeText(subject of forwardMessage)
        end try

        return my boolText(true) & fieldSeparator & subjectText & fieldSeparator & resolvedAccountLabel & recordSeparator
    end tell
end run
