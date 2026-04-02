on run argv
	tell application "Contacts"
		set totalCount to count of every person
		return "{" & quote & "ok" & quote & ":true," & quote & "count" & quote & ":" & totalCount & "}"
	end tell
end run
