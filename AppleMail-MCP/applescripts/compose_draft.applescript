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
    set toRaw to item 1 of argv
    set ccRaw to item 2 of argv
    set bccRaw to item 3 of argv
    set subjectText to item 4 of argv
    set bodyText to item 5 of argv
    set attachmentRaw to item 6 of argv

    set fieldSeparator to ASCII character 31
    set recordSeparator to ASCII character 30
    set listSeparator to ASCII character 29
    set toList to my splitText(toRaw, listSeparator)
    set ccList to my splitText(ccRaw, listSeparator)
    set bccList to my splitText(bccRaw, listSeparator)
    set attachmentList to my splitText(attachmentRaw, listSeparator)

    tell application "Mail"
        set newMessage to make new outgoing message with properties {visible:true, subject:subjectText, content:bodyText}
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
        return my sanitizeText((id of newMessage) as text) & fieldSeparator & my boolText(visible of newMessage) & recordSeparator
    end tell
end run
