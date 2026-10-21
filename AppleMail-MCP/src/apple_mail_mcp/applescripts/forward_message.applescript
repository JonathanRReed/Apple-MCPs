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
        -- Return a concrete account, not a live `item N of every account`
        -- loop reference (issue #23).
        repeat with accountRef in (get every account)
            set candidateAccount to contents of accountRef
            try
                if (name of candidateAccount as text) is senderRaw then
                    return candidateAccount
                end if
            end try
            try
                if (email addresses of candidateAccount) contains senderRaw then
                    return candidateAccount
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

on fullNameForAccount(theAccount)
    tell application "Mail"
        try
            return (full name of theAccount) as text
        end try
    end tell
    return ""
end fullNameForAccount

on emailForAccount(theAccount, senderRaw)
    tell application "Mail"
        try
            set addressList to email addresses of theAccount
            if senderRaw contains "@" then
                repeat with addressRef in addressList
                    if (addressRef as text) is senderRaw then
                        return addressRef as text
                    end if
                end repeat
            end if
            return item 1 of addressList as text
        end try
    end tell
    return ""
end emailForAccount

on senderStringForAccount(senderRaw, senderEmail, senderName)
    if senderEmail is "" then
        return senderRaw
    end if
    if senderName is "" then
        return senderEmail
    end if
    return senderName & " <" & senderEmail & ">"
end senderStringForAccount

on applySender(theMessage, senderRaw, senderEmail, senderString)
    -- Mail honours its own `sender` property when the address belongs to a
    -- configured account, so set it first. Only drive the From pop-up through
    -- System Events (separate Automation + Accessibility consent, and a hang
    -- while that consent is pending) when Mail did not take the value.
    set currentSender to ""
    tell application "Mail"
        set sender of theMessage to senderString
        delay 0.2
        try
            set currentSender to (sender of theMessage) as text
        end try
    end tell
    if my senderMatches(currentSender, senderRaw, senderEmail) then
        return currentSender
    end if
    return my selectSenderPopup(senderRaw, senderEmail)
end applySender

on parseMessageID(rawId)
    try
        set numericId to rawId as integer
    on error
        error "INVALID_MESSAGE_ID"
    end try
    -- Reject coercions such as 1.5 -> 2; never mutate a different message.
    if numericId < 0 or (numericId as text) is not rawId then
        error "INVALID_MESSAGE_ID"
    end if
    return numericId
end parseMessageID

on requireSingleMatch(matchedItems, missingCode, ambiguousCode)
    if (count of matchedItems) is 0 then error missingCode
    if (count of matchedItems) is not 1 then error ambiguousCode
    -- The caller supplies Mail's evaluated result, not a live every-item specifier.
    return contents of item 1 of matchedItems
end requireSingleMatch

on run argv
    set accountName to item 1 of argv
    set mailboxName to item 2 of argv
    set appleId to item 3 of argv
    set numericMessageId to my parseMessageID(appleId)
    set toRaw to item 4 of argv
    set forwardBody to item 5 of argv
    set senderRaw to item 6 of argv
    -- "false" leaves the forward open in Mail as an unsent draft for the user to review.
    set sendNow to true
    if (count of argv) ≥ 7 then set sendNow to ((item 7 of argv) is not "false")

    set listSeparator to ASCII character 29
    set fieldSeparator to ASCII character 31
    set recordSeparator to ASCII character 30
    set toList to my splitText(toRaw, listSeparator)

    set resolvedAccountLabel to ""
    set senderEmail to ""
    set senderString to ""

    tell application "Mail"
        -- Resolve concrete Mail objects and look the message up by id in one
        -- Apple event. Walking `id of` every message took minutes on a
        -- mailbox of a few thousand messages (issue #23 pattern, as in
        -- get_message.applescript).
        set sourceAccount to my requireSingleMatch((get every account whose name is accountName), "ACCOUNT_NOT_FOUND", "ACCOUNT_AMBIGUOUS")
        set sourceMailbox to my requireSingleMatch((get every mailbox of sourceAccount whose name is mailboxName), "MAILBOX_NOT_FOUND", "MAILBOX_AMBIGUOUS")
        try
            set targetMessage to (get first message of sourceMailbox whose id is numericMessageId)
        on error errorMessage number errorNumber
            if errorNumber is in {-1728, -1719} then error "MESSAGE_NOT_FOUND"
            error errorMessage number errorNumber
        end try
        if (id of targetMessage) is not numericMessageId then error "MESSAGE_ID_MISMATCH"

        set forwardMessage to forward targetMessage with opening window

        if forwardBody is not "" then
            set content of forwardMessage to forwardBody & return & return & content of forwardMessage
        end if

        if senderRaw is not "" then
            set matchedAccount to my resolveAccountBySender(senderRaw)
            set senderEmail to my emailForAccount(matchedAccount, senderRaw)
            set senderString to my senderStringForAccount(senderRaw, senderEmail, my fullNameForAccount(matchedAccount))
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
        set resolvedAccountLabel to my sanitizeText(my applySender(forwardMessage, senderRaw, senderEmail, senderString))
    end if

    tell application "Mail"
        if sendNow then
            send forwardMessage
        else
            -- Keep the compose window open; Mail autosaves it to Drafts.
            try
                save forwardMessage
            end try
        end if

        set subjectText to ""
        try
            set subjectText to my sanitizeText(subject of forwardMessage)
        end try

        return my boolText(sendNow) & fieldSeparator & subjectText & fieldSeparator & resolvedAccountLabel & recordSeparator
    end tell
end run
