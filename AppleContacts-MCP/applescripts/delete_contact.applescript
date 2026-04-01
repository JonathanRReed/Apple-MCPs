on run argv
    set contactId to item 1 of argv

    tell application "Contacts"
        set targetPerson to missing value
        repeat with thePerson in every person
            if (id of thePerson) is contactId then
                set targetPerson to thePerson
                exit repeat
            end if
        end repeat
        if targetPerson is missing value then
            return "{\"contact_id\":\"" & contactId & "\",\"deleted\":false}"
        end if

        delete targetPerson
        save

        return "{\"contact_id\":\"" & contactId & "\",\"deleted\":true}"
    end tell
end run
