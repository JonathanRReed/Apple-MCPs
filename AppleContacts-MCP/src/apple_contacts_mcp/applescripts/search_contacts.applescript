on run argv
	set queryText to item 1 of argv
	set jsonItems to {}
	tell application "Contacts"
		set matches to (every person whose name contains queryText or organization contains queryText)
		repeat with p in matches
			set end of jsonItems to my person_json(p, false)
		end repeat
	end tell
	return "{" & quote & "items" & quote & ":[" & my join_list(jsonItems, ",") & "]}"
end run

on person_json(p, includeNote)
	set contactId to ""
	set fullName to ""
	set firstName to ""
	set lastName to ""
	set organizationName to ""
	set noteText to ""
	set phoneItems to {}
	set phoneCount to 0
	set emailItems to {}
	set emailCount to 0
	tell application "Contacts"
		try
			set contactId to (id of p) as text
		on error
		end try
		try
			set fullName to (name of p) as text
		on error
		end try
		try
			set organizationName to (organization of p) as text
		on error
		end try
		try
			set rawPhones to phones of p
			set phoneItems to my method_json_list(rawPhones)
			set phoneCount to count of rawPhones
		on error
		end try
		try
			set rawEmails to emails of p
			set emailItems to my method_json_list(rawEmails)
			set emailCount to count of rawEmails
		on error
		end try
	end tell
	return "{" & ¬
		quote & "contact_id" & quote & ":" & my json_string(contactId) & "," & ¬
		quote & "name" & quote & ":" & my json_string(fullName) & "," & ¬
		quote & "first_name" & quote & ":" & my json_string(firstName) & "," & ¬
		quote & "last_name" & quote & ":" & my json_string(lastName) & "," & ¬
		quote & "organization" & quote & ":" & my json_string(organizationName) & "," & ¬
		quote & "phone_count" & quote & ":" & phoneCount & "," & ¬
		quote & "email_count" & quote & ":" & emailCount & "," & ¬
		quote & "phones" & quote & ":[" & my join_list(phoneItems, ",") & "]," & ¬
		quote & "emails" & quote & ":[" & my join_list(emailItems, ",") & "]," & ¬
		quote & "note" & quote & ":" & my json_string(noteText) & "}"
end person_json

on method_json_list(methodItems)
	set jsonItems to {}
	tell application "Contacts"
		repeat with methodItem in methodItems
			set end of jsonItems to "{" & quote & "label" & quote & ":" & my json_string(my safe_text(label of methodItem)) & "," & quote & "value" & quote & ":" & my json_string(my safe_text(value of methodItem)) & "}"
		end repeat
	end tell
	return jsonItems
end method_json_list

on safe_text(valueText)
	try
		return valueText as text
	on error
		return ""
	end try
end safe_text

on json_string(valueText)
	set backslash to ASCII character 92
	set escapedText to my replace_text(valueText as text, backslash, backslash & backslash)
	set escapedText to my replace_text(escapedText, quote, backslash & quote)
	set escapedText to my replace_text(escapedText, return, backslash & "n")
	set escapedText to my replace_text(escapedText, linefeed, backslash & "n")
	return quote & escapedText & quote
end json_string

on replace_text(sourceText, findText, replaceText)
	set originalDelimiters to AppleScript's text item delimiters
	set AppleScript's text item delimiters to findText
	set sourceItems to text items of sourceText
	set AppleScript's text item delimiters to replaceText
	set resultText to sourceItems as text
	set AppleScript's text item delimiters to originalDelimiters
	return resultText
end replace_text

on join_list(itemList, delimiterText)
	if (count of itemList) is 0 then
		return ""
	end if
	set originalDelimiters to AppleScript's text item delimiters
	set AppleScript's text item delimiters to delimiterText
	set joinedText to itemList as text
	set AppleScript's text item delimiters to originalDelimiters
	return joinedText
end join_list
