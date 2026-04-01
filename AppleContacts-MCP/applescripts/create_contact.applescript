on applyMethods(targetPerson, rawText, kindName, fieldSeparator, recordSeparator)
    if rawText is "" then
        return
    end if
    set previousDelimiters to AppleScript's text item delimiters
    set AppleScript's text item delimiters to recordSeparator
    set rawItems to text items of rawText
    set AppleScript's text item delimiters to previousDelimiters
    repeat with rawItem in rawItems
        if rawItem is not "" then
            set AppleScript's text item delimiters to fieldSeparator
            set parts to text items of rawItem
            set AppleScript's text item delimiters to previousDelimiters
            if (count of parts) is less than 2 then
                set parts to {}
            end if
        else
            set parts to {}
        end if
        if (count of parts) is greater than or equal to 2 then
            set labelText to item 1 of parts
            set valueText to item 2 of parts
            if kindName is "phone" then
                tell application "Contacts"
                    make new phone at end of phones of targetPerson with properties {label:labelText, value:valueText}
                end tell
            else if kindName is "email" then
                tell application "Contacts"
                    make new email at end of emails of targetPerson with properties {label:labelText, value:valueText}
                end tell
            end if
        end if
    end repeat
end applyMethods

on run argv
    set firstNameArg to item 1 of argv
    set lastNameArg to item 2 of argv
    set organizationArg to item 3 of argv
    set phonesArg to item 4 of argv
    set emailsArg to item 5 of argv
    set noteArg to item 6 of argv
    set fieldSeparator to ASCII character 31
    set recordSeparator to ASCII character 30

    tell application "Contacts"
        set newPerson to make new person with properties {first name:firstNameArg, last name:lastNameArg}

        if organizationArg is not "" then
            set organization of newPerson to organizationArg
        end if

        if noteArg is not "" then
            set note of newPerson to noteArg
        end if

        my applyMethods(newPerson, phonesArg, "phone", fieldSeparator, recordSeparator)
        my applyMethods(newPerson, emailsArg, "email", fieldSeparator, recordSeparator)

        save

        -- Return a simple JSON payload
        set contactId to id of newPerson
        set fullName to name of newPerson as text

        return "{\"contact_id\":\"" & contactId & "\",\"name\":\"" & fullName & "\",\"created\":true}"
    end tell
end run
