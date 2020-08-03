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
from common import FileHandler

import gettext
gettext.install("sticky", "/usr/share/locale", names="ngettext")

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
        self.title_box = Gtk.Box(height_request=30, name='title-box')
        self.connect('button-press-event', self.on_title_click)

        self.title = Gtk.Label(label=title)
        self.title_box.pack_start(self.title, False, False, 0)

        close_icon = Gtk.Image.new_from_icon_name('window-close', Gtk.IconSize.BUTTON)
        close_button = Gtk.Button(image=close_icon, relief=Gtk.ReliefStyle.NONE, name='window-button', valign=Gtk.Align.CENTER)
        close_button.connect('clicked', self.remove)
        close_button.connect('button-press-event', self.on_title_click)
        self.title_box.pack_end(close_button, False, False, 0)

        add_icon = Gtk.Image.new_from_icon_name('add', Gtk.IconSize.BUTTON)
        add_button = Gtk.Button(image=add_icon, relief=Gtk.ReliefStyle.NONE, name='window-button', valign=Gtk.Align.CENTER)
        add_button.connect('clicked', self.app.new_note)
        add_button.connect('button-press-event', self.on_title_click)
        self.title_box.pack_end(add_button, False, False, 0)

        test_icon = Gtk.Image.new_from_icon_name('system-run-symbolic', Gtk.IconSize.BUTTON)
        test_button = Gtk.Button(image=test_icon, relief=Gtk.ReliefStyle.NONE, name='window-button', valign=Gtk.Align.CENTER)
        test_button.connect('clicked', self.test)
        test_button.connect('button-press-event', self.on_title_click)
        self.title_box.pack_end(test_button, False, False, 0)

        self.set_titlebar(self.title_box)

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

            self.checklist_item = Gtk.MenuItem(label=_("Toggle Checklist"), visible=True)
            self.checklist_item.connect('activate', self.buffer.toggle_checklist)
            popup.append(self.checklist_item)

            self.bullet_item = Gtk.MenuItem(label=_("Toggle Bullets"), visible=True)
            self.bullet_item.connect('activate', self.buffer.toggle_bullets)
            popup.append(self.bullet_item)

            popup.append(Gtk.SeparatorMenuItem(visible=True))

        color_menu = Gtk.Menu()
        color_item = Gtk.MenuItem(label=_("Set Color"), submenu=color_menu, visible=True)
        popup.append(color_item)

        for color, color_name in COLORS.items():
            menu_item = Gtk.MenuItem(label=color_name, visible=True)
            menu_item.connect('activate', self.set_color, color)
            color_menu.append(menu_item)

        format_menu = Gtk.Menu()
        format_item = Gtk.MenuItem(label=_("Format"), submenu=format_menu, visible=True)
        popup.append(format_item)

        bold_item = Gtk.MenuItem(label=_("Bold"), visible=True)
        bold_item.connect('activate', self.apply_format, 'bold')
        format_menu.append(bold_item)

        italic_item = Gtk.MenuItem(label=_("Italic"), visible=True)
        italic_item.connect('activate', self.apply_format, 'italic')
        format_menu.append(italic_item)

        underline_item = Gtk.MenuItem(label=_("Underline"), visible=True)
        underline_item.connect('activate', self.apply_format, 'underline')
        format_menu.append(underline_item)

        label = _("Set Title") if self.title.get_text() == '' else _('Edit Title')
        edit_title = Gtk.MenuItem(label=label, visible=True)
        edit_title.connect('activate', self.set_title)
        popup.append(edit_title)

        remove_item = Gtk.MenuItem(label=_("Remove"), visible=True)
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

    def set_title(self, *args):
        self.title_text = self.title.get_text()
        self.title_box.remove(self.title)

        self.title = Gtk.Entry(text=self.title_text, visible=True)
        self.title_box.pack_start(self.title, True, True, 0)
        self.title.connect('key-press-event', self.save_title)
        self.title.connect('focus-out-event', self.save_title)

        self.title.grab_focus()

    def save_title(self, w, event):
        save = False
        enter_keys = (Gdk.KEY_Return, Gdk.KEY_ISO_Enter, Gdk.KEY_KP_Enter)
        if event.type == Gdk.EventType.FOCUS_CHANGE or event.keyval in enter_keys:
            self.title_text = self.title.get_text()
            save = True
        elif event.keyval != Gdk.KEY_Escape:
            return Gdk.EVENT_PROPAGATE

        self.view.grab_focus()

        self.title_box.remove(self.title)

        self.title = Gtk.Label(label=self.title_text, visible=True)
        self.title_box.pack_start(self.title, False, False, 0)

        if save:
            self.emit('update')

        return Gdk.EVENT_STOP

class SettingsWindow(XApp.PreferencesWindow):
    def __init__(self, app):
        super(SettingsWindow, self).__init__()

        # general settings
        general_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        general_page.pack_start(GSettingsSwitch(_("Show in Taskbar"), SCHEMA, 'show-in-taskbar'), False, False, 0)
        general_page.pack_start(GSettingsSwitch(_("Show Manager on Start"), SCHEMA, 'show-manager-on-start'), False, False, 0)
        general_page.pack_start(GSettingsSwitch(_("Show Notes on all Desktops"), SCHEMA, 'desktop-window-state'), False, False, 0)

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

class Application(Gtk.Application):
    dummy_window = None

    def __init__(self):
        super(Application, self).__init__(application_id=APPLICATION_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)

        self.notes = []
        self.settings_window = None
        self.manager = None

    def do_activate(self):
        Gtk.Application.do_activate(self)

        self.settings = Gio.Settings(schema_id=SCHEMA)

        self.file_handler = FileHandler(self.settings)

        self.settings.connect('changed::show-in-taskbar', self.update_dummy_window)
        self.update_dummy_window()

        self.note_group = self.settings.get_string('default-group')
        group_names = self.file_handler.get_note_group_names()
        if self.note_group not in group_names:
            if len(group_names) > 0:
                self.note_group = group_names[0]
            else:
                self.file_handler.update_note_list([], self.note_group)

        provider = Gtk.CssProvider()
        provider.load_from_path(STYLE_SHEET_PATH)

        Gtk.StyleContext.add_provider_for_screen (Gdk.Screen.get_default(), provider, 600)

        self.menu = Gtk.Menu()

        item = Gtk.MenuItem(label=_("New Note"))
        item.connect('activate', self.new_note)
        self.menu.append(item)

        item = Gtk.MenuItem(label=_("Manage Notes"))
        item.connect('activate', self.open_manager)
        self.menu.append(item)

        item = Gtk.MenuItem(label=_("Settings"))
        item.connect('activate', self.open_settings_window)
        self.menu.append(item)

        item = Gtk.MenuItem(label=_("Back Up Notes"))
        item.connect('activate', self.file_handler.save_backup)
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

        self.load_notes()

        if self.settings.get_boolean('show-manager-on-start'):
            self.open_manager()

        self.hold()

    def update_dummy_window(self, *args):
        if self.settings.get_boolean('show-in-taskbar'):
            self.dummy_window = Gtk.Window(default_height=1, default_width=1, decorated=False, deletable=False)
            if self.settings.get_boolean('desktop-window-state'):
                self.dummy_window.stick()
            self.dummy_window.show()

        elif self.dummy_window is not None:
            self.dummy_window.destroy()
            self.dummy_window = None

        for note in self.notes:
            note.set_transient_for(self.dummy_window)

    def activate_notes(self, i, b, time):
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
        self.generate_note()

    def generate_note(self, info={}):
        note = Note(self, info)
        note.connect('update', self.on_update)
        note.connect('removed', self.on_removed)

        if self.dummy_window:
            note.set_transient_for(self.dummy_window)

        self.notes.append(note)

    def load_notes(self):
        for note in self.notes:
            note.destroy()

        self.notes = []

        for note_info in self.file_handler.get_note_list(self.note_group):
            self.generate_note(note_info)

    def change_note_group(self, group=None):
        if group is None:
            self.note_group = self.settings.get_string('default-group')
        else:
            self.note_group = group

        self.load_notes()

    def open_manager(self, *args):
        if self.manager:
            self.manager.window.present()
            return

        self.manager = NotesManager(self, self.file_handler)
        self.manager.window.connect('destroy', self.manager_closed)

    def manager_closed(self, *args):
        self.manager = None

    def open_settings_window(self, *args):
        if self.settings_window:
            self.settings_window.present()
            return

        self.settings_window = SettingsWindow(self)
        self.settings_window.connect('destroy', self.settings_window_closed)

        self.settings_window.show_all()

    def settings_window_closed(self, *args):
        self.settings_window = None

    def on_update(self, *args):
        info = []
        for note in self.notes:
            info.append(note.get_info())

        self.file_handler.update_note_list(info, self.note_group)

    def on_removed(self, note):
        self.notes.remove(note)
        self.on_update()

    def quit_app(self, *args):
        self.file_handler.flush()

        for note in self.notes:
            note.destroy()

        self.quit()

if __name__ == "__main__":
    sticky = Application()
    sticky.run()
