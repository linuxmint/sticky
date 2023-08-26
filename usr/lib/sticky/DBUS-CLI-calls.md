# DBUS / CLI calls

Besides GUI interaction you can manipulate Sticky via dbus-send calls:

## CLI calls

### Notes

#### Toggle Notes
dbus-send --type="method_call" --dest=org.x.stickyapp /org/x/stickyapp org.x.stickyapp.activate_notes

#### Hide Notes

dbus-send --type="method_call" --dest=org.x.stickyapp /org/x/stickyapp org.x.stickyapp.hide_notes

#### New Note

dbus-send --type="method_call" --dest=org.x.stickyapp /org/x/stickyapp org.x.stickyapp.new_note

### Open notes manager

dbus-send --type="method_call" --dest=org.x.stickyapp /org/x/stickyapp org.x.stickyapp.open_manager 

### Quit app

dbus-send --type="method_call" --dest=org.x.stickyapp /org/x/stickyapp org.x.stickyapp.quit_app 


## DBUS calls (python example)

```
import dbus
from dbus.exceptions import DBusException
from sticky import BUS_NAME # BUS_NAME = SCHEMA + 'app' ##

bus = dbus.SessionBus()
try:
    object_path = '/'+BUS_NAME.replace('.','/')
    sticky_service = bus.get_object(bus_name=BUS_NAME, object_path=object_path)
except DBusException:
    print('ERROR: Sticky Notes app is not running!')
    exit()

method_names = ['activate_notes', 'hide_notes', 'new_note', 'open_manager', 'quit_app']

method = sticky_service.get_dbus_method(method_names[0], BUS_NAME)
method()

```

