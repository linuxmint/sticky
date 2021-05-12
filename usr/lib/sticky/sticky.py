#!/usr/bin/python3

import json
import os
import random

import gi
gi.require_version('Gdk', '3.0')
gi.require_version('Gspell', '1')
gi.require_version('Gtk', '3.0')
gi.require_version('XApp', '1.0')
from gi.repository import Gdk, Gio, GObject, Gspell, Gtk, Pango, XApp

from xapp.GSettingsWidgets import *

from note_buffer import NoteBuffer
from manager import NotesManager
from common import FileHandler, prompt, confirm
from util import gnote_to_internal_format

import gettext
gettext.install("sticky", "/usr/share/locale", names="ngettext")

import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
import names
import logging


APPLICATION_ID = 'org.x.sticky'
STYLE_SHEET_PATH = '/usr/share/sticky/sticky.css'
SCHEMA = 'org.x.sticky'

COLORS = {
    'red': _("Red"),
    'green': _("Green"),
    'blue': _("Blue"),
    'yellow': _("Yellow"),
    'purple': _("Purple"),
    'teal': _("Teal"),
    'orange': _("Orange"),
    'magenta': _("Magenta")
}

SHORTCUTS = [
    (_("Move selection up"), '<ctrl><shift>Up'),
    (_("Move selection down"), '<ctrl><shift>Down'),
    (_("Undo"), '<ctrl>z'),
    (_("Redo"), '<ctrl>y'),
    (_("Toggle Checklist"), '<ctrl>e'),
    (_("Toggle Bullets"), '<ctrl>l'),
    (_("Bold"), '<ctrl>b'),
    (_("Italic"), '<ctrl>i'),
    (_("Underline"), '<ctrl>u'),
    (_("Strikethrough"), '<ctrl>k'),
    (_("Highlight"), '<ctrl>g'),
    (_("Header"), '<ctrl>h')
]

class Note(Gtk.Window):
    @GObject.Signal(flags=GObject.SignalFlags.RUN_LAST, return_type=bool,
                    accumulator=GObject.signal_accumulator_true_handled)
    def update(self):
        pass

    @GObject.Signal(flags=GObject.SignalFlags.RUN_LAST, return_type=bool,
                    accumulator=GObject.signal_accumulator_true_handled)
    def removed(self):
        pass

    def __init__(self, app, info={}):
        self.app = app

        self.showing = False
        self.is_pinned = False

        self.x = info.get('x', 0)
        self.y = info.get('y', 0)
        self.height = info.get('height', self.app.settings.get_uint('default-height'))
        self.width = info.get('width', self.app.settings.get_uint('default-width'))
        title = info.get('title', '')
        text = info.get('text', '')
        self.color = info.get('color', self.app.settings.get_string('default-color'))

        super(Note, self).__init__(
            skip_taskbar_hint=True,
            # skip_pager_hint=False,
            type_hint=Gdk.WindowTypeHint.UTILITY,
            default_height=self.height,
            default_width=self.width,
            resizable=True,
            deletable=False,
            name='sticky-note'
        )

        if self.color == 'random':
            self.color = random.choice(list(COLORS.keys()))

        context = self.get_style_context()
        context.add_class(self.color)

        if self.app.settings.get_boolean('desktop-window-state'):
            self.stick()

        # title bar
        self.title_bar = Gtk.Box(height_request=30, name='title-box')
        self.connect('button-press-event', self.on_title_click)

        # formatting items are shown here
        more_menu_icon = Gtk.Image.new_from_icon_name('view-more', Gtk.IconSize.BUTTON)
        more_menu_button = Gtk.Button(image=more_menu_icon, relief=Gtk.ReliefStyle.NONE, name='window-button', valign=Gtk.Align.CENTER)
        more_menu_button.connect('clicked', self.show_more_menu)
        more_menu_button.connect('button-press-event', self.on_title_click)
        more_menu_button.set_tooltip_text(_("Format"))
        self.title_bar.pack_start(more_menu_button, False, False, 0)

        # used to show the edit title icon when the title is hovered
        self.title_hover = Gtk.EventBox()
        self.title_bar.pack_start(self.title_hover, True, True, 4)
        self.title_hover.connect('enter-notify-event', self.set_edit_button_visibility)
        self.title_hover.connect('leave-notify-event', self.set_edit_button_visibility)

        self.title_box = Gtk.Box()
        self.title_hover.add(self.title_box)
        self.title = Gtk.Label(label=title, margin_top=4)
        self.title_box.pack_start(self.title, False, False, 0)

        edit_title_icon = Gtk.Image.new_from_icon_name('edit', Gtk.IconSize.BUTTON)
        self.edit_title_button = Gtk.Button(image=edit_title_icon, relief=Gtk.ReliefStyle.NONE, name='window-button', valign=Gtk.Align.CENTER, no_show_all=True)
        self.edit_title_button.connect('clicked', self.set_title)
        self.edit_title_button.connect('button-press-event', self.on_title_click)
        self.edit_title_button.set_tooltip_text(_("Format"))
        self.title_box.pack_start(self.edit_title_button, False, False, 0)

        close_icon = Gtk.Image.new_from_icon_name('window-close', Gtk.IconSize.BUTTON)
        close_button = Gtk.Button(image=close_icon, relief=Gtk.ReliefStyle.NONE, name='window-button', valign=Gtk.Align.CENTER)
        close_button.connect('clicked', self.remove)
        close_button.connect('button-press-event', self.on_title_click)
        close_button.set_tooltip_text(_("Delete Note"))
        self.title_bar.pack_end(close_button, False, False, 0)

        add_icon = Gtk.Image.new_from_icon_name('add', Gtk.IconSize.BUTTON)
        add_button = Gtk.Button(image=add_icon, relief=Gtk.ReliefStyle.NONE, name='window-button', valign=Gtk.Align.CENTER)
        add_button.connect('clicked', self.app.new_note)
        add_button.connect('button-press-event', self.on_title_click)
        add_button.set_tooltip_text(_("New Note"))
        self.title_bar.pack_end(add_button, False, False, 0)

        # test_icon = Gtk.Image.new_from_icon_name('system-run-symbolic', Gtk.IconSize.BUTTON)
        # test_button = Gtk.Button(image=test_icon, relief=Gtk.ReliefStyle.NONE, name='window-button', valign=Gtk.Align.CENTER)
        # test_button.connect('clicked', self.test)
        # test_button.connect('button-press-event', self.on_title_click)
        # self.title_bar.pack_end(test_button, False, False, 0)

        self.set_titlebar(self.title_bar)

        # buffer
        self.buffer = NoteBuffer()

        # text view
        self.view = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, populate_all=True, buffer=self.buffer)
        self.buffer.set_view(self.view)
        spell_checker = Gspell.TextView.get_from_gtk_text_view(self.view)
        spell_checker.basic_setup()
        self.app.settings.bind('inline-spell-check', spell_checker, 'inline-spell-checking', Gio.SettingsBindFlags.GET)
        self.view.set_left_margin(10)
        self.view.set_right_margin(10)
        self.view.set_top_margin(10)
        self.view.set_bottom_margin(10)
        self.view.connect('populate-popup', lambda w, p: self.add_context_menu_items(p))
        self.view.connect('key-press-event', self.on_key_press)

        scroll = Gtk.ScrolledWindow()
        self.add(scroll)
        scroll.add(self.view)

        self.buffer.set_from_internal_markup(text)
        self.changed_id = self.buffer.connect('content-changed', self.changed)

        self.connect('configure-event', self.handle_update)
        self.connect('show', self.on_show)
        self.connect('window-state-event', self.update_window_state)

        self.move(self.x, self.y)

        self.show_all()

    def test(self, *args):
        self.buffer.test()

    def handle_update(self, *args):
        if self.showing:
            self.showing = False
            return

        (new_x, new_y) = self.get_position()
        (new_width, new_height) = self.get_size()
        if self.x == new_x and self.y == new_y and self.height == new_height and self.width == new_width:
            return

        self.x = new_x
        self.y = new_y
        self.height = new_height
        self.width = new_width
        self.emit('update')

    def on_show(self, *args):
        self.showing = True

    def on_key_press(self, v, event):
        if event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            if event.get_state() & Gdk.ModifierType.SHIFT_MASK:
                if event.get_keyval()[1] == Gdk.KEY_Up:
                    self.buffer.shift(True)
                    return Gdk.EVENT_STOP

                elif event.get_keyval()[1] == Gdk.KEY_Down:
                    self.buffer.shift(False)
                    return Gdk.EVENT_STOP

            if event.get_keyval()[1] == Gdk.KEY_z:
                self.buffer.undo()
                return Gdk.EVENT_STOP

            elif event.get_keyval()[1] == Gdk.KEY_y:
                self.buffer.redo()
                return Gdk.EVENT_STOP

            elif event.get_keyval()[1] == Gdk.KEY_e:
                self.buffer.toggle_checklist()
                return Gdk.EVENT_STOP

            elif event.get_keyval()[1] == Gdk.KEY_l:
                self.buffer.toggle_bullets()
                return Gdk.EVENT_STOP

            elif event.get_keyval()[1] == Gdk.KEY_b:
                self.buffer.tag_selection('bold')
                return Gdk.EVENT_STOP

            elif event.get_keyval()[1] == Gdk.KEY_i:
                self.buffer.tag_selection('italic')
                return Gdk.EVENT_STOP

            elif event.get_keyval()[1] == Gdk.KEY_u:
                self.buffer.tag_selection('underline')
                return Gdk.EVENT_STOP

            elif event.get_keyval()[1] == Gdk.KEY_h:
                self.buffer.tag_selection('header')
                return Gdk.EVENT_STOP

            elif event.get_keyval()[1] == Gdk.KEY_k:
                self.buffer.tag_selection('strikethrough')
                return Gdk.EVENT_STOP

            elif event.get_keyval()[1] == Gdk.KEY_g:
                self.buffer.tag_selection('highlight')
                return Gdk.EVENT_STOP

        elif event.keyval in (Gdk.KEY_Return, Gdk.KEY_ISO_Enter, Gdk.KEY_KP_Enter):
            return self.buffer.on_return()

        return Gdk.EVENT_PROPAGATE

    def update_window_state(self, w, event):
        self.is_stuck = event.new_window_state & Gdk.WindowState.STICKY
        # for some reason, the ABOVE flag is never actually being set, even when it should be
        # self.is_pinned = event.new_window_state & Gdk.WindowState.ABOVE

    def on_title_click(self, w, event):
        if event.button == 3:
            menu = Gtk.Menu()
            self.add_context_menu_items(menu, True)
            menu.popup(None, None, None, None, event.button, event.time)

            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    def restore(self, time=0):
        if not self.get_visible():
            self.present_with_time(time)
            self.move(self.x, self.y)

        self.get_window().focus(time)
        self.get_window().raise_()

    def changed(self, *args):
        self.emit('update')

    def get_info(self):
        (x, y) = self.get_position()
        (width, height) = self.get_size()
        info = {
            'x': x,
            'y': y,
            'height': height,
            'width': width,
            'color': self.color,
            'title': self.title.get_text(),
            'text': self.buffer.get_internal_markup()
        }

        return info

    def add_context_menu_items(self, popup, is_title=False):
        if not is_title:
            popup.append(Gtk.SeparatorMenuItem(visible=True))

            self.undo_item = Gtk.MenuItem(label=_("undo"), visible=True, sensitive=self.buffer.can_undo)
            self.undo_item.connect('activate', self.buffer.undo)
            popup.append(self.undo_item)

            self.redo_item = Gtk.MenuItem(label=_("redo"), visible=True, sensitive=self.buffer.can_redo)
            self.redo_item.connect('activate', self.buffer.redo)
            popup.append(self.redo_item)

            popup.append(Gtk.SeparatorMenuItem(visible=True))

        label = _("Set Title") if self.title.get_text() == '' else _('Edit Title')
        edit_title = Gtk.MenuItem(label=label, visible=True)
        edit_title.connect('activate', self.set_title)
        popup.append(edit_title)

        remove_item = Gtk.MenuItem(label=_("Remove Note"), visible=True)
        remove_item.connect('activate', self.remove)
        popup.append(remove_item)

        if is_title:
            popup.append(Gtk.SeparatorMenuItem(visible=True))

            if self.is_stuck:
                label = _("Only on This Workspace")
                def on_activate(*args):
                    self.unstick()
            else:
                label = _("Always on Visible Workspace")
                def on_activate(*args):
                    self.stick()

            stick_menu_item = Gtk.MenuItem(label=label, visible=True)
            stick_menu_item.connect('activate', on_activate)
            popup.append(stick_menu_item)

            def on_activate(*args):
                self.set_keep_above(not self.is_pinned)
                self.is_pinned = not self.is_pinned

            pin_menu_item = Gtk.CheckMenuItem(active=self.is_pinned, label=_("Always on Top"), visible=True)
            pin_menu_item.connect('activate', on_activate)
            popup.append(pin_menu_item)

    def show_more_menu(self, button):
        menu = Gtk.Menu()

        color_menu = Gtk.Menu()
        color_item = Gtk.MenuItem(label=_("Set Note Color"), submenu=color_menu, visible=True)
        menu.append(color_item)

        for color, color_name in COLORS.items():
            menu_item = Gtk.MenuItem(label=color_name, visible=True)
            menu_item.connect('activate', self.set_color, color)
            color_menu.append(menu_item)

        menu.append(Gtk.SeparatorMenuItem(visible=True))

        self.checklist_item = Gtk.MenuItem(label=_("Toggle Checklist"), visible=True)
        self.checklist_item.connect('activate', self.buffer.toggle_checklist)
        menu.append(self.checklist_item)

        self.bullet_item = Gtk.MenuItem(label=_("Toggle Bullets"), visible=True)
        self.bullet_item.connect('activate', self.buffer.toggle_bullets)
        menu.append(self.bullet_item)

        menu.append(Gtk.SeparatorMenuItem(visible=True))

        bold_item = Gtk.MenuItem(label=_("Bold"), visible=True)
        bold_item.connect('activate', self.apply_format, 'bold')
        menu.append(bold_item)

        italic_item = Gtk.MenuItem(label=_("Italic"), visible=True)
        italic_item.connect('activate', self.apply_format, 'italic')
        menu.append(italic_item)

        underline_item = Gtk.MenuItem(label=_("Underline"), visible=True)
        underline_item.connect('activate', self.apply_format, 'underline')
        menu.append(underline_item)

        strikethrough_item = Gtk.MenuItem(label=_("Strikethrough"), visible=True)
        strikethrough_item.connect('activate', self.apply_format, 'strikethrough')
        menu.append(strikethrough_item)

        highlight_item = Gtk.MenuItem(label=_("Highlight"), visible=True)
        highlight_item.connect('activate', self.apply_format, 'highlight')
        menu.append(highlight_item)

        header_item = Gtk.MenuItem(label=_("Header"), visible=True)
        header_item.connect('activate', self.apply_format, 'header')
        menu.append(header_item)

        menu.popup_at_widget(button, Gdk.Gravity.SOUTH, Gdk.Gravity.NORTH_WEST, None)

    def set_color(self, menu, color):
        if color == self.color:
            return

        self.get_style_context().remove_class(self.color)
        self.get_style_context().add_class(color)
        self.color = color

        self.emit('update')

    def apply_format(self, m, format_type):
        self.buffer.tag_selection(format_type)

    def remove(self, *args):
        self.emit('removed')
        self.destroy()

    def set_edit_button_visibility(self, *args):
        pointer_device = self.get_display().get_default_seat().get_pointer()
        (mouse_x, mouse_y) = self.title_hover.get_window().get_device_position(pointer_device)[1:3]
        dimensions = self.title_hover.get_allocation()

        has_mouse = mouse_x >= 0 and mouse_x < dimensions.width and mouse_y >= 0 and mouse_y < dimensions.height

        if not isinstance(self.title, Gtk.Entry) and has_mouse:
            self.edit_title_button.show()
        else:
            self.edit_title_button.hide()

    def set_title(self, *args):
        self.title_text = self.title.get_text()
        self.title_box.remove(self.title)

        self.title = Gtk.Entry(text=self.title_text, visible=True)
        self.title_box.pack_start(self.title, False, False, 0)

        self.title.key_id = self.title.connect('key-press-event', self.save_title)
        self.title.focus_id = self.title.connect('focus-out-event', self.save_title)

        self.title_box.reorder_child(self.title, 0)
        self.set_edit_button_visibility()

        self.title.grab_focus()

    def save_title(self, w, event):
        save = False
        if event.type == Gdk.EventType.FOCUS_CHANGE:
            save = True
        else:
            if event.keyval in (Gdk.KEY_Return, Gdk.KEY_ISO_Enter, Gdk.KEY_KP_Enter):
                save = True
            elif event.keyval != Gdk.KEY_Escape:
                return Gdk.EVENT_PROPAGATE

        self.title.disconnect(self.title.key_id)
        self.title.disconnect(self.title.focus_id)

        if save:
            self.title_text = self.title.get_text()

        self.view.grab_focus()

        self.title_box.remove(self.title)

        self.title = Gtk.Label(label=self.title_text, visible=True)
        self.title_box.pack_start(self.title, False, False, 0)

        self.title_box.reorder_child(self.title, 0)
        self.set_edit_button_visibility()

        if save:
            self.emit('update')

        return Gdk.EVENT_STOP

class SettingsWindow(XApp.PreferencesWindow):
    def __init__(self, app):
        super(SettingsWindow, self).__init__()

        # general settings
        general_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        general_page.pack_start(GSettingsSwitch(_("Show Notes on all Desktops"), SCHEMA, 'desktop-window-state'), False, False, 0)
        general_page.pack_start(GSettingsSwitch(_("Show Status Icon in Tray"), SCHEMA, 'show-in-tray'), False, False, 0)
        dep = SCHEMA + '/show-in-tray'
        general_page.pack_start(GSettingsSwitch(_("Show Manager on Start"), SCHEMA, 'show-manager-on-start', dep_key=dep), False, False, 0)
        general_page.pack_start(GSettingsSwitch(_("Show in Taskbar"), SCHEMA, 'show-in-taskbar', dep_key=dep), False, False, 0)

        self.add_page(general_page, 'general', _("General"))

        # note related settings
        notes_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        notes_page.pack_start(GSettingsSpinButton(_("Default Height"), SCHEMA, 'default-height', mini=50, maxi=2000, step=10), False, False, 0)
        notes_page.pack_start(GSettingsSpinButton(_("Default Width"), SCHEMA, 'default-width', mini=50, maxi=2000, step=10), False, False, 0)
        try:
            colors = [(x, y) for x, y in COLORS.items()]
            colors.append(('sep', ''))
            colors.append(('random', _('Random')))

            notes_page.pack_start(GSettingsComboBox(_("Default Color"), SCHEMA, 'default-color', options=colors, valtype=str, separator='sep'), False, False, 0)
        except Exception as e:
            colors = [(x, y) for x, y in COLORS.items()]
            colors.append(('random', _('Random')))

            notes_page.pack_start(GSettingsComboBox(_("Default Color"), SCHEMA, 'default-color', options=colors, valtype=str), False, False, 0)

        notes_page.pack_start(GSettingsSwitch(_("Show Spelling Mistakes"), SCHEMA, 'inline-spell-check'), False, False, 0)

        self.add_page(notes_page, 'notes', _("Notes"))

        # backups
        backup_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        backup_page.pack_start(GSettingsSwitch(_("Create Periodic Backups"), SCHEMA, 'automatic-backups'), False, False, 0)
        backup_page.pack_start(GSettingsSpinButton(_("Time Between Backups"), SCHEMA, 'backup-interval', units=_("hours")), False, False, 0)
        obm_tooltip = _("Set this to zero if you wish to keep all backups indefinitely")
        backup_page.pack_start(GSettingsSpinButton(_("Number to Keep"), SCHEMA, 'old-backups-max', tooltip=obm_tooltip), False, False, 0)

        self.add_page(backup_page, 'backup', _("Backups"))

        self.show_all()

class ShortcutsWindow(Gtk.ShortcutsWindow):
    def __init__(self):
        super(ShortcutsWindow, self).__init__()

        section = Gtk.ShortcutsSection(visible=True)

        group = Gtk.ShortcutsGroup(title='editing', visible=True)
        section.add(group)

        for shortcut in SHORTCUTS:
            shortcut_item = Gtk.ShortcutsShortcut(title=shortcut[0], accelerator=shortcut[1], visible=True)
            group.add(shortcut_item)

        self.add(section)
        self.show_all()

class Application(Gtk.Application):
    dummy_window = None
    status_icon = None
    has_activated = False

    @GObject.Signal(flags=GObject.SignalFlags.RUN_LAST, return_type=bool,
                    accumulator=GObject.signal_accumulator_true_handled)
    def visible_group_changed(self):
        pass

    def __init__(self):
        super(Application, self).__init__(application_id=APPLICATION_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)

        self.notes = []
        self.settings_window = None
        self.keyboard_shortcuts = None
        self.manager = None

    def do_activate(self):
        if self.has_activated:
            for note in self.notes:
                note.restore()

            return

        Gtk.Application.do_activate(self)

        self.settings = Gio.Settings(schema_id=SCHEMA)

        self.file_handler = FileHandler(self.settings)

        if self.settings.get_boolean('first-run'):
            self.first_run()

        self.file_handler.connect('lists-changed', self.on_lists_changed)
        self.group_update_id = self.file_handler.connect('group-changed', self.on_group_changed)

        if self.settings.get_boolean('show-in-tray'):
            self.create_status_icon()

            if self.settings.get_boolean('show-manager-on-start'):
                self.open_manager()
        else:
            self.open_manager()

        self.settings.connect('changed::show-in-tray', self.update_tray_icon)
        self.settings.connect('changed::show-in-taskbar', self.update_dummy_window)
        self.update_dummy_window()

        self.note_group = self.settings.get_string('default-group')
        group_names = self.file_handler.get_note_group_names()
        if self.note_group not in group_names:
            if len(group_names) > 0:
                self.note_group = group_names[0]
            else:
                self.file_handler.new_group(self.note_group)

        provider = Gtk.CssProvider()
        provider.load_from_path(STYLE_SHEET_PATH)

        Gtk.StyleContext.add_provider_for_screen (Gdk.Screen.get_default(), provider, 600)

        self.load_notes()

        self.hold()

        self.has_activated = True

    def first_run(self):
        gnote_dir = os.path.join(GLib.get_user_data_dir(), 'gnote')

        if os.path.exists(gnote_dir):
            contents = os.listdir(gnote_dir)

            import_notes = []
            for file in contents:
                path = os.path.join(gnote_dir, file)
                if os.path.isfile(path) and path.endswith('.note'):
                    import_notes.append(path)

            if len(import_notes) > 0:
                resp = confirm(_("Sticky Notes"),
                              _("Would you like to import your notes from Gnote? This will not change your Gnote notes in any way."))

                if resp:
                    for file in import_notes:
                        (group_name, info) = gnote_to_internal_format(file)

                        color = self.settings.get_string('default-color')
                        if color == 'random':
                            info['color'] = random.choice(list(COLORS.keys()))
                        else:
                            info['color'] = color

                        if group_name not in self.file_handler.get_note_group_names():
                            self.file_handler.new_group(group_name)

                        group_list = self.file_handler.get_note_list(group_name)
                        group_list.append(info)
                        self.file_handler.update_note_list(group_list, group_name)

        self.settings.set_boolean('first-run', False)

    def create_status_icon(self):
        self.menu = Gtk.Menu()

        item = Gtk.MenuItem(label=_("New Note"))
        item.connect('activate', self.new_note)
        self.menu.append(item)

        item = Gtk.MenuItem(label=_("Manage Notes"))
        item.connect('activate', self.open_manager)
        self.menu.append(item)

        self.menu.append(Gtk.SeparatorMenuItem())

        self.group_menu = Gtk.Menu()
        item = Gtk.MenuItem(label=_("Change Group"), submenu=self.group_menu)
        self.menu.append(item)

        self.update_groups_menu()

        self.menu.append(Gtk.SeparatorMenuItem())

        item = Gtk.MenuItem(label=_("Back Up Notes"))
        item.connect('activate', self.file_handler.save_backup)
        self.menu.append(item)

        item = Gtk.MenuItem(label=_("Back Up To File"))
        item.connect('activate', self.file_handler.backup_to_file)
        self.menu.append(item)

        item = Gtk.MenuItem(label=_("Restore Backup"))
        item.connect('activate', self.file_handler.restore_backup)
        self.menu.append(item)

        self.menu.append(Gtk.SeparatorMenuItem())

        item = Gtk.MenuItem(label=_("Settings"))
        item.connect('activate', self.open_settings_window)
        self.menu.append(item)

        item = Gtk.MenuItem(label=_("Keyboard Shortcuts"))
        item.connect('activate', self.open_keyboard_shortcuts)
        self.menu.append(item)

        self.menu.append(Gtk.SeparatorMenuItem())

        item = Gtk.MenuItem(label=_("Exit"))
        item.connect('activate', self.quit_app)
        self.menu.append(item)

        self.menu.show_all()

        self.status_icon = XApp.StatusIcon()
        self.status_icon.set_name('sticky')
        self.status_icon.set_icon_name('sticky-symbolic')
        self.status_icon.set_tooltip_text('Sticky Notes')
        self.status_icon.set_visible(True)
        self.status_icon.set_secondary_menu(self.menu)
        self.status_icon.connect('activate', self.activate_notes)

    def destroy_status_icon(self):
        self.status_icon.set_visible(False)
        self.status_icon = None
        self.menu = None

    def update_tray_icon(self, *args):
        if self.settings.get_boolean('show-in-tray'):
            self.create_status_icon()
        else:
            self.open_manager()
            self.destroy_status_icon()

    def update_dummy_window(self, *args):
        if self.settings.get_boolean('show-in-taskbar'):
            self.dummy_window = Gtk.Window(name=_("Sticky Notes"), default_height=1, default_width=1, decorated=False, deletable=False)
            if self.settings.get_boolean('desktop-window-state'):
                self.dummy_window.stick()
            self.dummy_window.show()

        elif self.dummy_window is not None:
            self.dummy_window.destroy()
            self.dummy_window = None

        for note in self.notes:
            note.set_transient_for(self.dummy_window)

    def activate_notes(self, i, b, time):
        self.do_activate_notes(time)

    def do_activate_notes(self, time=0):
        for note in self.notes:
            if note.is_active():
                self.hide_notes()
                return

        for note in self.notes:
            note.restore(time)

    def hide_notes(self):
        for note in self.notes:
            note.hide()

    def new_note(self, *args):
        note = self.generate_note()
        note.present()

    def generate_note(self, info={}):
        note = Note(self, info)
        note.connect('update', self.on_update)
        note.connect('removed', self.on_removed)

        if self.dummy_window:
            note.set_transient_for(self.dummy_window)

        self.notes.append(note)

        return note

    def new_group(self, *args):
        (response, new_group_name) = prompt(_("New Group"), _("Choose a name for the new group"))

        if not response:
            return

        if new_group_name == "":
            message = Gtk.MessageDialog(text=_("Cannot create group without a name"), buttons=Gtk.ButtonsType.CLOSE)
            message.run()
            message.destroy()
        elif new_group_name in self.file_handler.get_note_group_names():
            message = Gtk.MessageDialog(text=_("Cannot create group: the name %s already exists") % new_group_name,
                                        buttons=Gtk.ButtonsType.CLOSE)
            message.run()
            message.destroy()
        else:
            self.file_handler.new_group(new_group_name)
            self.change_visible_note_group(new_group_name)
            self.new_note()

    def load_notes(self):
        for note in self.notes:
            note.destroy()

        self.notes = []

        for note_info in self.file_handler.get_note_list(self.note_group):
            self.generate_note(note_info)

    def update_groups_menu(self):
        for item in self.group_menu.get_children():
            item.destroy()

        item = Gtk.MenuItem(label=_("New Group"))
        item.connect('activate', self.new_group)
        self.group_menu.append(item)

        self.group_menu.append(Gtk.SeparatorMenuItem())

        for group in self.file_handler.get_note_group_names():
            item = Gtk.MenuItem(label=group)
            item.connect('activate', lambda a, group: self.change_visible_note_group(group), group)
            self.group_menu.append(item)

        self.group_menu.show_all()

    def on_lists_changed(self, *args):
        if self.status_icon:
            self.update_groups_menu()

        if not self.note_group in self.file_handler.get_note_group_names():
            self.change_visible_note_group()
        else:
            self.load_notes()

    def on_group_changed(self, f, group_name):
        if self.note_group == group_name:
            self.load_notes()

    def change_visible_note_group(self, group=None):
        if group is None:
            self.note_group = self.settings.get_string('default-group')
        else:
            self.note_group = group

        self.load_notes()

        self.emit('visible-group-changed')

    def open_manager(self, *args):
        if self.manager:
            self.manager.window.present()
            return

        self.manager = NotesManager(self, self.file_handler)
        self.manager.window.connect('destroy', self.manager_closed)

    def manager_closed(self, *args):
        self.manager = None
        if self.status_icon is None:
            self.quit_app()

    def open_settings_window(self, *args):
        if self.settings_window:
            self.settings_window.present()
            return

        self.settings_window = SettingsWindow(self)
        self.settings_window.connect('destroy', self.settings_window_closed)

        self.settings_window.show_all()

    def settings_window_closed(self, *args):
        self.settings_window = None

    def open_keyboard_shortcuts(self, *args):
        if self.keyboard_shortcuts:
            self.keyboard_shortcuts.present()
            return

        self.keyboard_shortcuts = ShortcutsWindow()
        self.keyboard_shortcuts.connect('destroy', self.keyboard_shortcuts_closed)

        self.keyboard_shortcuts.show_all()

    def keyboard_shortcuts_closed(self, *args):
        self.keyboard_shortcuts = None

    def on_update(self, *args):
        info = []
        for note in self.notes:
            info.append(note.get_info())

        self.file_handler.handler_block(self.group_update_id)
        self.file_handler.update_note_list(info, self.note_group)
        self.file_handler.handler_unblock(self.group_update_id)

    def on_removed(self, note):
        self.notes.remove(note)
        self.on_update()

    def quit_app(self, *args):
        self.file_handler.flush()

        for note in self.notes:
            note.destroy()

        self.quit()


class DbusService(dbus.service.Object):

    def __init__(self, sticky):
        bus_name = dbus.service.BusName(names.bus_name, bus=dbus.SessionBus())
        dbus.service.Object.__init__(self, bus_name, names.object_path)
        self._sticky = sticky

    @dbus.service.method(dbus_interface=names.bus_name)
    def activate_notes(self):
        self._sticky.do_activate_notes()

    @dbus.service.method(dbus_interface=names.bus_name)
    def hide_notes(self):
        self._sticky.hide_notes()

    @dbus.service.method(dbus_interface=names.bus_name)
    def new_note(self):
        self._sticky.new_note()

    @dbus.service.method(dbus_interface=names.bus_name)
    def new_group(self):
        self._sticky.new_group()

    @dbus.service.method(dbus_interface=names.bus_name)
    def change_visible_note_group(self, group=None):
        logging.debug(f'Changing note group to {group}')
        self._sticky.change_visible_note_group(group)

    @dbus.service.method(dbus_interface=names.bus_name)
    def open_manager(self):
        self._sticky.open_manager()

    @dbus.service.method(dbus_interface=names.bus_name)
    def open_settings_window(self):
        self._sticky.open_settings_window()

    @dbus.service.method(dbus_interface=names.bus_name)
    def open_keyboard_shortcuts(self):
        self._sticky.open_keyboard_shortcuts()

    @dbus.service.method(dbus_interface=names.bus_name)
    def quit_app(self):
        self._sticky.quit_app()

global logger
logger = logging.getLogger(__name__)
logging.basicConfig(level='DEBUG')

if __name__ == "__main__":
    DBusGMainLoop(set_as_default=True)
    sticky = Application()
    dbusService = DbusService(sticky)
    sticky.run()
