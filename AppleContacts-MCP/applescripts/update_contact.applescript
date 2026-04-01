on applyMethods(targetPerson, rawText, kindName, fieldSeparator, recordSeparator)
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
    set contactId to item 1 of argv
    set firstNameArg to item 2 of argv
    set lastNameArg to item 3 of argv
    set organizationArg to item 4 of argv
    set phonesArg to item 5 of argv
    set emailsArg to item 6 of argv
    set noteArg to item 7 of argv
    set fieldSeparator to ASCII character 31
    set recordSeparator to ASCII character 30
    set noChangeSentinel to "__NOCHANGE__"

    tell application "Contacts"
        set targetPerson to missing value
        repeat with thePerson in every person
            if (id of thePerson) is contactId then
                set targetPerson to thePerson
                exit repeat
            end if
        end repeat
        if targetPerson is missing value then
            error "CONTACT_NOT_FOUND"
        end if

        if firstNameArg is not "" then
            set first name of targetPerson to firstNameArg
        end if

        if lastNameArg is not "" then
            set last name of targetPerson to lastNameArg
        end if

        if organizationArg is not "" then
            set organization of targetPerson to organizationArg
        end if

        if phonesArg is not noChangeSentinel then
            delete every phone of targetPerson
            my applyMethods(targetPerson, phonesArg, "phone", fieldSeparator, recordSeparator)
        end if

        if emailsArg is not noChangeSentinel then
            delete every email of targetPerson
            my applyMethods(targetPerson, emailsArg, "email", fieldSeparator, recordSeparator)
        end if

        if noteArg is not "" then
            set note of targetPerson to noteArg
        end if

        save

        set fullName to name of targetPerson as text
        return "{\"contact_id\":\"" & contactId & "\",\"name\":\"" & fullName & "\",\"updated\":true}"
    end tell
end run
