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

on normalizeText(valueText)
    if valueText is missing value then
        return ""
    end if
    set normalizedText to do shell script "/bin/echo " & quoted form of (valueText as text) & " | /usr/bin/tr '[:upper:]' '[:lower:]'"
    return normalizedText
end normalizeText

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

on senderMatches(candidateText, senderRaw, senderEmail)
    set normalizedCandidate to my normalizeText(candidateText)
    if senderEmail is not "" then
        set normalizedEmail to my normalizeText(senderEmail)
        if normalizedCandidate contains normalizedEmail then
            return true
        end if
    end if
    if senderRaw is not "" then
        set normalizedSender to my normalizeText(senderRaw)
        if normalizedCandidate contains normalizedSender then
            return true
        end if
    end if
    return false
end senderMatches

on currentSenderMatches(senderRaw, senderEmail)
    tell application "System Events"
        tell process "Mail"
            set frontmost to true
            set composeWindow to front window
            repeat with popupRef in every pop up button of composeWindow
                try
                    set currentValue to value of popupRef as text
                    if my senderMatches(currentValue, senderRaw, senderEmail) then
                        return currentValue
                    end if
                end try
            end repeat
        end tell
    end tell
    return ""
end currentSenderMatches

on selectSenderPopup(senderRaw, senderEmail)
    tell application "Mail" to activate
    repeat with attemptIndex from 1 to 5
        delay 0.3
        set currentMatch to my currentSenderMatches(senderRaw, senderEmail)
        if currentMatch is not "" then
            return currentMatch
        end if
        tell application "System Events"
            tell process "Mail"
                set frontmost to true
                set composeWindow to front window
                repeat with popupRef in every pop up button of composeWindow
                    click popupRef
                    delay 0.25
                    set matchingItem to missing value
                    try
                        repeat with menuItemRef in every menu item of menu 1 of popupRef
                            set itemName to name of menuItemRef as text
                            if my senderMatches(itemName, senderRaw, senderEmail) then
                                set matchingItem to menuItemRef
                                exit repeat
                            end if
                        end repeat
                    end try
                    if matchingItem is not missing value then
                        click matchingItem
                        delay 0.4
                        set updatedMatch to my currentSenderMatches(senderRaw, senderEmail)
                        if updatedMatch is not "" then
                            return updatedMatch
                        end if
                    end if
                    key code 53
                    delay 0.1
                end repeat
            end tell
        end tell
    end repeat
    error "ACCOUNT_MENU_ITEM_NOT_FOUND"
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
            delay 0.2
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
