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
            set fromPopup to first pop up button of composeWindow whose name is "From:"
            click fromPopup
            delay 0.2
            set matchingItem to missing value
            repeat with menuItemRef in every menu item of menu 1 of fromPopup
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
            if matchingItem is missing value then
                key code 53
                error "ACCOUNT_MENU_ITEM_NOT_FOUND"
            end if
            click matchingItem
            delay 0.3
            return value of fromPopup as text
        end tell
    end tell
end selectSenderPopup

on run argv
    set toRaw to item 1 of argv
    set ccRaw to item 2 of argv
    set bccRaw to item 3 of argv
    set subjectText to item 4 of argv
    set bodyText to item 5 of argv
    set attachmentRaw to item 6 of argv
    set senderRaw to item 7 of argv

    set fieldSeparator to ASCII character 31
    set recordSeparator to ASCII character 30
    set listSeparator to ASCII character 29
    set toList to my splitText(toRaw, listSeparator)
    set ccList to my splitText(ccRaw, listSeparator)
    set bccList to my splitText(bccRaw, listSeparator)
    set attachmentList to my splitText(attachmentRaw, listSeparator)

    set resolvedAccountLabel to ""
    set senderEmail to ""

    tell application "Mail"
        set forceVisible to false
        if senderRaw is not "" then
            set forceVisible to true
        end if
        set newMessage to make new outgoing message with properties {visible:forceVisible, subject:subjectText, content:bodyText}
        if senderRaw is not "" then
            set matchedAccount to my resolveAccountBySender(senderRaw)
            set senderEmail to my primaryEmailForAccount(matchedAccount)
            set sender of newMessage to senderRaw
        end if
        tell newMessage
            repeat with addressText in toList
                if (addressText as text) is not "" then
                    make new to recipient at end of to recipients with properties {address:addressText as text}
                end if
            end repeat
            repeat with addressText in ccList
                if (addressText as text) is not "" then
                    make new cc recipient at end of cc recipients with properties {address:addressText as text}
                end if
            end repeat
            repeat with addressText in bccList
                if (addressText as text) is not "" then
                    make new bcc recipient at end of bcc recipients with properties {address:addressText as text}
                end if
            end repeat
            repeat with attachmentPath in attachmentList
                if (attachmentPath as text) is not "" then
                    make new attachment with properties {file name:(POSIX file (attachmentPath as text))} at after the last paragraph
                end if
            end repeat
        end tell
    end tell

    if senderRaw is not "" then
        set resolvedAccountLabel to my sanitizeText(my selectSenderPopup(senderRaw, senderEmail))
    end if

    tell application "Mail"
        send newMessage
    end tell
    return "true" & fieldSeparator & my sanitizeText(subjectText) & fieldSeparator & resolvedAccountLabel & recordSeparator
end run
