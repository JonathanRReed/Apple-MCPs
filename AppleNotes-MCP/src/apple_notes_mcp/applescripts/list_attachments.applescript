on run argv
	set targetNoteId to item 1 of argv
	set jsonItems to {}
	set noteLocation to my find_note_location(targetNoteId)
	if noteLocation is missing value then
		return "{" & quote & "items" & quote & ":[]}"
	end if
	set n to item 5 of noteLocation
	tell application "Notes"
		repeat with a in attachments of n
			set end of jsonItems to "{" & quote & "name" & quote & ":" & my json_string(my safe_text(name of a)) & "}"
		end repeat
	end tell
	return "{" & quote & "items" & quote & ":[" & my join_list(jsonItems, ",") & "]}"
end run

on find_note_location(targetNoteId)
	-- Look the note up by id, then find its folder's account. Only if that
	-- fails, scan folder by folder, reading every note id of a folder in one
	-- Apple Event instead of one event per note.
	try
		tell application "Notes"
			set directNote to note id targetNoteId
			set directFolder to container of directNote
			set directFolderId to my safe_text(id of directFolder)
			repeat with acc in accounts
				set accountFolderIds to id of folders of acc
				repeat with accountFolderId in accountFolderIds
					considering case
						set folderMatches to (my safe_text(contents of accountFolderId)) is directFolderId
					end considering
					if folderMatches then
						return {my safe_text(id of acc), my safe_text(name of acc), directFolderId, my safe_text(name of directFolder), directNote}
					end if
				end repeat
			end repeat
		end tell
	end try
	tell application "Notes"
		repeat with acc in accounts
			set accName to my safe_text(name of acc)
			set accId to my safe_text(id of acc)
			repeat with fld in folders of acc
				set fldId to my safe_text(id of fld)
				set fldName to my safe_text(name of fld)
				set folderNoteIds to id of every note of fld
				repeat with i from 1 to count of folderNoteIds
					if my safe_text(item i of folderNoteIds) is targetNoteId then
						set candidateNote to note i of fld
						if my safe_text(id of candidateNote) is targetNoteId then return {accId, accName, fldId, fldName, candidateNote}
						-- The folder changed since its ids were read; check note by note.
						repeat with n in notes of fld
							if my safe_text(id of n) is targetNoteId then return {accId, accName, fldId, fldName, n}
						end repeat
					end if
				end repeat
			end repeat
		end repeat
	end tell
	return missing value
end find_note_location

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
