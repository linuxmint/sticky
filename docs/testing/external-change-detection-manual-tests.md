## Feature: External file change detection

### Manual Testing Scenarios

Test 1a: External change with no unsaved changes
START application
CREATE a new note in color yellow with text "demo note"
EXTERNALLY modify notes.json, (e.g., from text editor) changing color to red.
VERIFY dialog appears: The notes have been changed on disk. Do you want to reload all notes? Reload/Cancel
CLICK "Reload"
VERIFY UI the note color is now red.

Test 1b: Manager thumbnails refresh after reload
START application
OPEN notes manager
EXTERNALLY modify notes.json (change note text to "Thumbnail Test")
VERIFY External Change dialog appears
CLICK "Reload"
VERIFY manager window thumbnails are refreshed and show "Thumbnail Test"

Test 2: App's own save doesn't trigger dialog
START application
MAKE an edit to a note
WAIT 3 seconds for auto-save
VERIFY no dialog appears (ignore_next_change flag works)

Test 3: Backup files don't trigger dialog
START application
CHOOSE "Back up" from the 3-dot menu.
VERIFY backup-*.json is created
VERIFY no dialog appears (monitoring only notes.json)

Test 4a: User cancels reload, doesn't lose external changes
START application
EXTERNALLY modify notes.json: change note color to green.
VERIFY dialog appears.
CLICK "Cancel".
VERIFY UI remains unchanged.
CHANGE note text to "Happy Days"
WAIT 3 seconds.
A dialog should appear: notes.json has been modified since you last opened it. If you save now, those external changes will be lost. Do you want to save anyway? Don't Save/Backup and Save/Save Anyway.
CLICK "Save Anyway"
VERIFY notes.json has note text "Happy Days"

Test 4b:
Repeat 4a but choose "Don't Save".
Verify the UI is unchanged and the notes.json file is unchanged.

Test 4c: Backup and Save feature
Repeat 4a but choose "Backup and Save"
VERIFY notes.json has note text "Happy Days"
VERIFY a backup file has been created without text "Happy Days"

Test 5a: External change with unsaved changes (race condition)
START application
OPEN notes.json in external editor. Enter a note text of "Quick Fox" but don't save it yet.
MOVE the note, changing its position on the screen, (triggers 3-second save timer)
QUICKLY, within 3 seconds: save the EXTERNALLY modified notes.json.
VERIFY dialog appears with conflict message: The notes have been changed on disk, but you have unsaved changes. What would you like to do? Keep my changes/Reload from disk.
CLICK "Reload from disk"
Verify note has text "Quick Fox" and note is restored to original position.

Test 5b:
Repeat 5a except CLICK "Keep my changes"
VERIFY a second dialog appears with file modified message: The notes.json file has been modified since you last opened it. If you save now, those external changes will be lost. Do you want to save anyway? Don't Save/Backup and Save/Save Anyway.
CLICK "Save Anyway"
VERIFY UI keeps edited version with text "Lazy Dog"
VERIFY external changes are overwritten ("Quick Fox" is deleted).

Test 5c:
Repeat 5b except instead of 'Save Anyway' CLICK "Backup and Save"
VERIFY backup-*.json file is created containing "Quick Fox"
VERIFY notes.json contains the moved note position (user's changes)
VERIFY external edit "External Edit" is NOT in notes.json

Test 5d:
Repeat 5b except instead of 'Save Anyway' CLICK "Don't Save"
VERIFY notes.json is UNCHANGED (still has "Quick Fox")
VERIFY UI still shows moved position (changes in memory)
MOVE note again, wait 3 seconds
VERIFY File Modified dialog appears again

Test 6: Verify 'dirty flag' operation
OBSERVE last modified date on notes.json file.
START application
QUIT application
VERIFY last modified date on notes.json file is unchanged.

OBSERVE last modified date on notes.json file.
START application
Change the color of a note and within 3 seconds, QUIT application.
VERIFY last modified date on notes.json file is changed to reflect the time of Quit.

OBSERVE last modified date on notes.json file.
START application
Change the color of a note and wait 3 seconds for save operation.
VERIFY last modified date on notes.json file is changed to the time of the save.
QUIT application, wait 3 seconds.
VERIFY last modified date on notes.json file is unchanged.

Test 7a:  Confirmation dialog doesn't appear if notes are hidden, only when visible.
START application
VERIFY Tray icon is displayed (Preference > General > Tray icon)
Click the tray icon to hide the notes.
EXTERNALLY modify notes.json, (e.g., from text editor) changing color to red.
VERIFY confirmation dialog does NOT appear.
Click the tray icon to show the notes.
VERIFY confirmation dialog appears.
CHOOSE "reload" in the dialog.
VERIFY external modification is reflected in the notes.

Test 7b: Deferred dialog with after two modifications
Click the tray icon to hide the notes.
EXTERNALLY modify notes.json, save, then make a second modification and save.
VERIFY confirmation dialog does NOT appear.
Click the tray icon to show the notes.
VERIFY a single confirmation dialog appears.
CHOOSE "reload" in the dialog.
VERIFY both external modifications are reflected in the notes.

Test 7c: Deferred dialog with "Cancel" choice
START application
VERIFY Tray icon is displayed
Click the tray icon to hide the notes.
EXTERNALLY modify notes.json (change color to purple)
VERIFY confirmation dialog does NOT appear.
Click the tray icon to show the notes.
VERIFY External Change dialog appears.
CLICK "Cancel" (keep current in-memory state)
CHANGE note text to "Fat cat"), wait 3 seconds for save
VERIFY File Modified dialog appears (because external changes still pending)
CLICK "Save Anyway"
VERIFY notes.json contains "Fat cat" and does NOT have purple color

Test 8a: Creating notes through note manager.
START application
VERIFY Tray icon is displayed (Preference > General > Tray icon)
Click the tray icon to hide the notes.
EXTERNALLY modify notes.json.
VERIFY confirmation dialog doesn't appear.
In notes manager, create a new note. Wait 3 seconds.
VERIFY File Modified dialog appears.

Test 8b: Opening manager triggers deferred dialog
START application
VERIFY Tray icon is displayed
CLOSE notes manager (if open)
Click the tray icon to hide the notes
EXTERNALLY modify notes.json (change color to orange)
VERIFY confirmation dialog does NOT appear.
OPEN notes manager (right-click on tray icon)
VERIFY External Change dialog appears immediately (before manager window opens)
CLICK "Reload"
VERIFY notes have orange color
VERIFY manager window opens and shows updated thumbnails

Test 9a: Verify focus is returned to notes after dialog closes (both dialogs).
START application
CREATE a new note in color yellow with text "demo note", wait 3 seconds
EXTERNALLY modify notes.json, changing color to red
VERIFY dialog appears with title "External Change Detected" and buttons "Cancel" / "Reload"
CLICK "Reload from Disk"
VERIFY the note color is now red
CLICK the tray icon
VERIFY the notes are hidden on the FIRST click (focus is properly restored after dialog)

Test 9b:
Repeat 9a, except hide notes before external change.

Test 9c:
Repeat 9a, except CLICK "Cancel"
EDIT the note text to "Groovy Note"), wait 3 seconds
VERIFY File Modified dialog appears
CLICK "Save Anyway"
CLICK the tray icon
VERIFY notes are hidden on the FIRST click (focus properly restored)

Test 10: "Save anyway" cancels external pending changes
START application
VERIFY Tray icon is displayed (Preference > General > Tray icon)
Click the tray icon to hide the notes.
EXTERNALLY modify notes.json.
VERIFY confirmation dialog doesn't appear.
In notes manager, create a new note. Wait 3 seconds.
VERIFY File Modified dialog appears.
CLICK "Save Anyway" (overwriting pending external changes)
CLICK tray icon (even though notes are already visible)
Verify no confirmation dialog is presented.

Test 11: Quit with dirty changes and deferred external change
START application
VERIFY Tray icon is displayed
Click the tray icon to hide the notes.
EXTERNALLY modify notes.json (add "Slick note")
VERIFY confirmation dialog does NOT appear.
Click the tray icon to show the notes.
VERIFY External Change dialog appears.
CLICK "Cancel"
EDIT a note (change text to "About to quit")
IMMEDIATELY (within 1-2 seconds, before save timer fires) QUIT application
VERIFY File Modified dialog appears before application quits
CLICK "Don't Save"
OBSERVE the application is terminated.
RESTART application
VERIFY notes now contain the external modification "Slick note", (not "About to quit")

Test 12: "Backup and Save" clears pending external changes
START application
VERIFY Tray icon is displayed
Click the tray icon to hide the notes.
EXTERNALLY modify notes.json (change color to cyan)
VERIFY confirmation dialog does NOT appear.
In notes manager, create a new note. Wait 3 seconds.
VERIFY File Modified dialog appears.
CLICK "Backup and Save"
VERIFY backup-*.json is created with cyan color
VERIFY notes.json contains the new note.
Click the tray icon to hide notes.
Click the tray icon to show notes again.
VERIFY no External Change dialog appears (pending external change was cleared)

Test 13: Multiple external changes while dialog is open (notes visible)
START application
EXTERNALLY modify notes.json (change color to blue)
VERIFY External Change dialog appears
DO NOT respond to the dialog yet (leave it open)
EXTERNALLY modify notes.json again (change title to "HELLO")
CLICK "Reload" on the first dialog
VERIFY notes have blue color and title "HELLO" (both external changes applied)
OBSERVE a second External Change dialog appears immediately
CLICK "Reload" on the second dialog
VERIFY notes unchanged.
NOTE: Sequential dialogs are expected behavior due to GTK modal dialog blocking

Test 14: First launch scenario
COPY notes.json to a backup location.
RENAME notes.json to notes.json.bak
START application (simulating first launch)
CREATE a new note
WAIT 3 seconds
VERIFY no false dialogs appear
VERIFY notes.json is created correctly
QUIT application.
RESTORE original notes.json (delete test file)

Test 15: Obscure edge case anomaly
START application
VERIFY Tray icon is displayed (Preference > General > Tray icon)
Click the tray icon to hide the notes.
EXTERNALLY modify notes.json.
VERIFY confirmation dialog doesn't appear.
In notes manager, create a new note. Wait 3 seconds.
VERIFY File Modified dialog appears.
Click "Don't Save"
Hidden note reappears and notes.json is unchanged.
Make a second external change to the notes.json file.
Verify confirmation prompt does not appear.
(Because we haven't actually clicked the tray icon to make notes appear ... they showed up as a byproduct of other actions)

Test 16: Checkbox for "Always auto-reload" 
START application
VERIFY Preference > General > Auto reload is OFF.
CREATE a new note in color yellow with text "demo note"
EXTERNALLY modify notes.json, changing color to red.
VERIFY confirmation prompt appears with checkbox unchecked "Always reload (unless turned off in Preferences)"
CLICK the checkbox to turn on this preference.
CLICK "Reload"
VERIFY UI the note color is now red.
VERIFY Preference setting is now ON.
EXTERNALLY modify notes.json, changing color to blue.
VERIFY note color changes to blue WITHOUT confirmation prompt.
HIDE the notes, modify notes.json to change color to green.
REVEAL the notes, VERIFY the note is green (no prompt displayed)
MODIFY Preference setting to OFF.
EXTERNALLY modify notes.json, changing color to teal.
VERIFY confirmation prompt appears with checkbox unchecked "Always reload (unless turned off in Preferences)"
CLICK "Reload"
VERIFY UI the note color is now teal.

Test 17: Auto-reload doesn't happen in race condition.
VERIFY auto-reload preference is ON.
Repeat test 5 for race condition and verify confirmation prompt appears even though auto-reload is on.

