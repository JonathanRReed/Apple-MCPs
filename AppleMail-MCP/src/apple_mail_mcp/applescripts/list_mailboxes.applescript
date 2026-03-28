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
    return safeText
end sanitizeText

on run argv
    set requestedAccount to ""
    if (count of argv) > 0 then
        set requestedAccount to item 1 of argv
    end if

    set fieldSeparator to ASCII character 31
    set recordSeparator to ASCII character 30
    set rows to {}

    tell application "Mail"
        repeat with theAccount in every account
            set accountName to name of theAccount
            if requestedAccount is "" or accountName is requestedAccount then
                repeat with theMailbox in every mailbox of theAccount
                    set end of rows to my sanitizeText(accountName) & fieldSeparator & my sanitizeText(name of theMailbox)
                end repeat
            end if
        end repeat
    end tell

    return my joinText(rows, recordSeparator)
end run
