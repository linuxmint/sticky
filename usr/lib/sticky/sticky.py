#!/usr/bin/python3

import json
import os
import sys

import gi
gi.require_version('Gdk', '3.0')
gi.require_version('Gspell', '1')
gi.require_version('Gtk', '3.0')
gi.require_version('XApp', '1.0')
from gi.repository import Gdk, Gio, GObject, Gspell, Gtk, Pango, XApp

from xapp.GSettingsWidgets import *

from note_buffer import NoteBuffer
from manager import NotesManager
from common import FileHandler, HoverBox, prompt, confirm
from util import gnote_to_internal_format

import gettext
gettext.install("sticky", "/usr/share/locale", names="ngettext")

APPLICATION_ID = 'org.x.sticky'
STYLE_SHEET_PATH = '/usr/share/sticky/sticky.css'
SCHEMA = 'org.x.sticky'

UPDATE_DELAY = 1

FONT_SCALES = [
    ('small', _("Small Text"), 'small'),
    ('normal', _("Normal Text"), 'medium'),
    ('large', _("Large Text"), 'large'),
    ('larger', _("Larger Text"), 'x-large')
]

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

COLOR_CODES = {
    'red': "#ff5561",
    'green': "#67ff67",
    'blue': "#3d9bff",
    'yellow': "#f6f907",
    'purple': "#a553ff",
    'teal': "#41ffed",
    'orange': "#ffa939",
    'magenta': "#ff7ff7"
}

SHORTCUTS = {
    _("Operations"): [
        (_("Move selection up"), '<ctrl><shift>Up'),
        (_("Move selection down"), '<ctrl><shift>Down'),
        (_("Undo"), '<ctrl>z'),
        (_("Redo"), '<ctrl>y'),
        (_("Toggle Checklist"), '<ctrl>e'),
        (_("Toggle Bullets"), '<ctrl>l')
    ],
    _("Formatting"): [
        (_("Bold"), '<ctrl>b'),
        (_("Italic"), '<ctrl>i'),
        (_("Fixed Width"), '<ctrl>f'),
        (_("Underline"), '<ctrl>u'),
        (_("Strikethrough"), '<ctrl>k'),
        (_("Highlight"), '<ctrl>g'),
        (_("Header"), '<ctrl>h')
    ]
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

    def __init__(self, app, parent, info={}):
        self.app = app

        self.showing = False
        self.is_pinned = False
        self.changed_timer_id = 0

        self.x = info.get('x', 0)
        self.y = info.get('y', 0)
        self.height = info.get('height', self.app.settings.get_uint('default-height'))
        self.width = info.get('width', self.app.settings.get_uint('default-width'))
        title = info.get('title', '')
        text = info.get('text', '')
        self.color = info.get('color', self.app.settings.get_string('default-color'))

        super(Note, self).__init__(
            skip_taskbar_hint=True,
            transient_for=parent,
            type_hint=Gdk.WindowTypeHint.UTILITY,
            default_height=self.height,
            default_width=self.width,
            resizable=True,
            deletable=False,
            name='sticky-note'
        )

        if self.color == 'cycle':
            if self.app.settings.get_string('last-color') == '':
                last_color = self.color
            else:
                last_color = self.app.settings.get_string('last-color')

            color_keys = list(COLORS)
            try:
                self.color = color_keys[color_keys.index(last_color) + 1]
            except (ValueError, IndexError):
                self.color = color_keys[0]

            self.app.settings.set_string('last-color', self.color)

        context = self.get_style_context()
        context.add_class(self.color)

        if self.app.settings.get_boolean('desktop-window-state'):
            self.stick()

        # title bar
        self.title_bar = Gtk.Box(height_request=30, name='title-bar')
        self.title_bar.connect('button-press-event', self.on_title_click)

        color_icon = Gtk.Image.new_from_icon_name('sticky-color', Gtk.IconSize.BUTTON)
        color_button = Gtk.MenuButton(image=color_icon, relief=Gtk.ReliefStyle.NONE, name='window-button', valign=Gtk.Align.CENTER)
        color_button.connect('button-press-event', self.on_title_click)
        color_button.set_tooltip_text(_("Note Color"))
        self.title_bar.pack_start(color_button, False, False, 0)

        # used to show the edit title icon when the title is hovered
        self.title_hover = HoverBox()
        self.title_bar.pack_start(self.title_hover, True, True, 4)

        self.title_box = Gtk.Box()
        self.title_hover.add(self.title_box)
        self.title = Gtk.Label(label=title, margin_top=4, name='title')
        self.title_box.pack_start(self.title, False, False, 0)
        self.title_style_manager = XApp.StyleManager(widget=self.title_box)

        edit_title_icon = Gtk.Image.new_from_icon_name('sticky-edit', Gtk.IconSize.BUTTON)
        self.edit_title_button = Gtk.Button(image=edit_title_icon, relief=Gtk.ReliefStyle.NONE, name='window-button', valign=Gtk.Align.CENTER)
        self.edit_title_button.connect('clicked', self.set_title)
        self.edit_title_button.connect('button-press-event', self.on_title_click)
        self.edit_title_button.set_tooltip_text(_("Rename"))
        self.title_box.pack_start(self.edit_title_button, False, False, 0)
        self.title_hover.set_child_widget(self.edit_title_button)

        close_icon = Gtk.Image.new_from_icon_name('sticky-delete', Gtk.IconSize.BUTTON)
        close_button = Gtk.Button(image=close_icon, relief=Gtk.ReliefStyle.NONE, name='window-button', valign=Gtk.Align.CENTER)
        close_button.connect('clicked', self.remove)
        close_button.connect('button-press-event', self.on_title_click)
        close_button.set_tooltip_text(_("Delete Note"))
        self.title_bar.pack_end(close_button, False, False, 0)

        add_icon = Gtk.Image.new_from_icon_name('sticky-add', Gtk.IconSize.BUTTON)
        add_button = Gtk.Button(image=add_icon, relief=Gtk.ReliefStyle.NONE, name='window-button', valign=Gtk.Align.CENTER)
        add_button.connect('clicked', self.app.new_note)
        add_button.connect('button-press-event', self.on_title_click)
        add_button.set_tooltip_text(_("New Note"))
        self.title_bar.pack_end(add_button, False, False, 0)

        text_icon = Gtk.Image.new_from_icon_name('sticky-text', Gtk.IconSize.BUTTON)
        text_button = Gtk.MenuButton(image=text_icon, relief=Gtk.ReliefStyle.NONE, name='window-button', valign=Gtk.Align.CENTER)
        text_button.connect('button-press-event', self.on_title_click)
        text_button.set_tooltip_text(_("Format"))
        self.title_bar.pack_end(text_button, False, False, 20)

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
        self.view_style_manager = XApp.StyleManager(widget=self.view)

        scroll = Gtk.ScrolledWindow()
        self.add(scroll)
        scroll.add(self.view)

        self.buffer.set_from_internal_markup(text)
        self.changed_id = self.buffer.connect('content-changed', self.queue_update)

        self.app.settings.connect('changed::font', self.set_font)
        self.set_font()

        self.create_format_menu(color_button, text_button)

        self.connect('configure-event', self.on_size_position_changed)
        self.connect('show', self.on_show)
        self.connect('window-state-event', self.update_window_state)

        self.move(self.x, self.y)

        self.show_all()

    def test(self, *args):
        self.buffer.test()

    def on_size_position_changed(self, *args):
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

        self.queue_update()

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

            elif event.get_keyval()[1] == Gdk.KEY_f:
                self.buffer.tag_selection('monospace')
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

            elif event.get_keyval()[1] == Gdk.KEY_2:
                self.buffer.tag_selection('small')
                return Gdk.EVENT_STOP

            elif event.get_keyval()[1] == Gdk.KEY_3:
                self.buffer.tag_selection('normal')
                return Gdk.EVENT_STOP

            elif event.get_keyval()[1] == Gdk.KEY_4:
                self.buffer.tag_selection('large')
                return Gdk.EVENT_STOP

            elif event.get_keyval()[1] == Gdk.KEY_5:
                self.buffer.tag_selection('larger')
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
        if time == 0:
            time = Gtk.get_current_event_time()

        self.show()
        self.present_with_time(time)
        self.move(self.x, self.y)

    def queue_update(self, *args):
        if self.changed_timer_id:
            GLib.source_remove(self.changed_timer_id)

        self.changed_timer_id = GLib.timeout_add_seconds(UPDATE_DELAY, self.trigger_update)

    def trigger_update(self):
        self.changed_timer_id = 0

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

        remove_item = Gtk.MenuItem(label=_("Delete Note"), visible=True)
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

    def create_format_menu(self, color_button, text_button):

        menu = Gtk.Menu()

        for color, color_name in sorted(COLORS.items(), key=lambda item: item[1]):
            color_code = COLOR_CODES[color]
            menu_item = Gtk.MenuItem(label=color_name, visible=True)
            menu_item.get_child().set_markup("<span foreground='%s'>\u25A6</span>  %s" % (color_code, color_name))
            menu_item.connect('activate', self.set_color, color)
            menu.append(menu_item)

        color_button.set_popup(menu)

        menu = Gtk.Menu()

        bold_item = Gtk.MenuItem(label=_("Bold"), visible=True)
        bold_item.get_child().set_markup("<b>%s</b>" % _("Bold"))
        bold_item.connect('activate', self.apply_format, 'bold')
        menu.append(bold_item)

        italic_item = Gtk.MenuItem(label=_("Italic"), visible=True)
        italic_item.get_child().set_markup("<i>%s</i>" % _("Italic"))
        italic_item.connect('activate', self.apply_format, 'italic')
        menu.append(italic_item)

        monospace_item = Gtk.MenuItem(label=_("Fixed Width"), visible=True)
        monospace_item.get_child().set_markup("<tt>%s</tt>" % _("Fixed Width"))
        monospace_item.connect('activate', self.apply_format, 'monospace')
        menu.append(monospace_item)

        underline_item = Gtk.MenuItem(label=_("Underline"), visible=True)
        underline_item.get_child().set_markup("<u>%s</u>" % _("Underline"))
        underline_item.connect('activate', self.apply_format, 'underline')
        menu.append(underline_item)

        strikethrough_item = Gtk.MenuItem(label=_("Strikethrough"), visible=True)
        strikethrough_item.get_child().set_markup("<s>%s</s>" % _("Strikethrough"))
        strikethrough_item.connect('activate', self.apply_format, 'strikethrough')
        menu.append(strikethrough_item)

        highlight_item = Gtk.MenuItem(label=_("Highlight"), visible=True)
        highlight_item.get_child().set_markup("<span background='yellow' foreground='black'>%s</span>" % _("Highlight"))
        highlight_item.connect('activate', self.apply_format, 'highlight')
        menu.append(highlight_item)

        header_item = Gtk.MenuItem(label=_("Header"), visible=True)
        header_item.get_child().set_markup("<span size='large'>%s</span>" % _("Header"))
        header_item.connect('activate', self.apply_format, 'header')
        menu.append(header_item)

        menu.append(Gtk.SeparatorMenuItem(visible=True))

        for (scale_id, scale_name, scale_value) in FONT_SCALES:
            font_scale_item = Gtk.MenuItem(label=scale_name, visible=True)
            font_scale_item.get_child().set_markup("<span size='%s'>%s</span>" % (scale_value, scale_name))
            font_scale_item.connect('activate', self.apply_format, scale_id)
            menu.append(font_scale_item)

        menu.append(Gtk.SeparatorMenuItem(visible=True))

        self.checklist_item = Gtk.MenuItem(label="\u25A2 %s" % _("Toggle Checklist"), visible=True)
        self.checklist_item.connect('activate', self.buffer.toggle_checklist)
        menu.append(self.checklist_item)

        self.bullet_item = Gtk.MenuItem(label="\u25CF %s" % _("Toggle Bullets"), visible=True)
        self.bullet_item.connect('activate', self.buffer.toggle_bullets)
        menu.append(self.bullet_item)

        text_button.set_popup(menu)

    def set_color(self, menu, color):
        if color == self.color:
            return

        self.get_style_context().remove_class(self.color)
        self.get_style_context().add_class(color)
        self.color = color

        self.emit('update')

    def set_font(self, *args):
        self.title_style_manager.set_from_pango_font_string(self.app.settings.get_string('font'))
        self.view_style_manager.set_from_pango_font_string(self.app.settings.get_string('font'))

    def apply_format(self, m, format_type):
        self.buffer.tag_selection(format_type)

    def remove(self, *args):
        # this is ugly but I'm not sure how to make it look better :)
        if (self.app.settings.get_boolean('disable-delete-confirm') or
            (not self.title.get_text() and self.buffer.get_char_count() == 0) or
            confirm(_("Delete Note"), _("Are you sure you want to remove this note?"),
                    self, self.app.settings, 'disable-delete-confirm')):
            self.emit('removed')
            self.destroy()

    def set_title(self, *args):
        self.title_text = self.title.get_text()
        self.title_box.remove(self.title)

        self.title = Gtk.Entry(text=self.title_text, visible=True, name='title')
        self.title_box.pack_start(self.title, False, False, 0)

        self.title.key_id = self.title.connect('key-press-event', self.save_title)
        self.title.focus_id = self.title.connect('focus-out-event', self.save_title)

        self.title_box.reorder_child(self.title, 0)
        self.title_hover.disable()

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

        self.title = Gtk.Label(label=self.title_text, visible=True, name='title')
        self.title_box.pack_start(self.title, False, False, 0)

        self.title_box.reorder_child(self.title, 0)
        self.title_hover.enable()

        if save:
            self.emit('update')

        return Gdk.EVENT_STOP

class SettingsWindow(XApp.PreferencesWindow):
    def __init__(self, app):
        super(SettingsWindow, self).__init__(skip_taskbar_hint=False, title=_("Preferences"))

        # general settings
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        page.pack_start(GSettingsSwitch(_("Show notes on all desktops"), SCHEMA, 'desktop-window-state'), False, False, 0)
        page.pack_start(GSettingsSwitch(_("Show in taskbar"), SCHEMA, 'show-in-taskbar'), False, False, 0)
        page.pack_start(GSettingsSwitch(_("Tray icon"), SCHEMA, 'show-in-tray'), False, False, 0)
        page.pack_start(GSettingsSwitch(_("Show the main window automatically"), SCHEMA, 'show-manager', dep_key=SCHEMA+'/show-in-tray'), False, False, 0)
        self.add_page(page, 'general', _("General"))

        # note related settings
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        page.pack_start(GSettingsSpinButton(_("Default height"), SCHEMA, 'default-height', mini=50, maxi=2000, step=10), False, False, 0)
        page.pack_start(GSettingsSpinButton(_("Default width"), SCHEMA, 'default-width', mini=50, maxi=2000, step=10), False, False, 0)
        try:
            colors = [(x, y) for x, y in COLORS.items()]
            colors.append(('sep', ''))
            colors.append(('cycle', _('Cycle Colors')))

            page.pack_start(GSettingsComboBox(_("Default color"), SCHEMA, 'default-color', options=colors, valtype=str, separator='sep'), False, False, 0)
        except Exception as e:
            colors = [(x, y) for x, y in COLORS.items()]
            colors.append(('cycle', _('Cycle Colors')))

            page.pack_start(GSettingsComboBox(_("Default color"), SCHEMA, 'default-color', options=colors, valtype=str), False, False, 0)

        page.pack_start(GSettingsFontButton(_("Font"), SCHEMA, 'font', level=Gtk.FontChooserLevel.SIZE), False, False, 0)
        page.pack_start(GSettingsSwitch(_("Show spelling mistakes"), SCHEMA, 'inline-spell-check'), False, False, 0)

        self.add_page(page, 'notes', _("Notes"))

        # backups
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        page.pack_start(GSettingsSwitch(_("Automatic backups"), SCHEMA, 'automatic-backups'), False, False, 0)
        page.pack_start(GSettingsSpinButton(_("Time between backups"), SCHEMA, 'backup-interval', units=_("hours")), False, False, 0)
        obm_tooltip = _("Set this to zero if you wish to keep all backups indefinitely")
        page.pack_start(GSettingsSpinButton(_("Number to keep"), SCHEMA, 'old-backups-max', tooltip=obm_tooltip), False, False, 0)

        self.add_page(page, 'backup', _("Backups"))

        # autostart
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        page.pack_start(GSettingsSwitch(_("Start automatically"), SCHEMA, 'autostart'), False, False, 0)
        page.pack_start(GSettingsSwitch(_("Show notes on the screen"), SCHEMA, 'autostart-notes-visible', dep_key=SCHEMA+'/autostart'), False, False, 0)
        self.add_page(page, 'autostart', _("Automatic start"))

        self.show_all()

class ShortcutsWindow(Gtk.ShortcutsWindow):
    def __init__(self):
        super(ShortcutsWindow, self).__init__()

        section = Gtk.ShortcutsSection(visible=True)

        for group, items in SHORTCUTS.items():
            group = Gtk.ShortcutsGroup(title=group, visible=False)
            section.add(group)

            for shortcut in items:
                shortcut_item = Gtk.ShortcutsShortcut(title=shortcut[0], accelerator=shortcut[1], visible=True)
                group.add(shortcut_item)

        group = Gtk.ShortcutsGroup(title=_("Text Size"), visible=False)
        section.add(group)
        for i in range(len(FONT_SCALES)):
            shortcut_item = Gtk.ShortcutsShortcut(title=FONT_SCALES[i][1], accelerator='<ctrl>%d' % (i + 2), visible=True)
            group.add(shortcut_item)

        self.add(section)
        self.show_all()

class Application(Gtk.Application):

    def __init__(self):
        super(Application, self).__init__(application_id=APPLICATION_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)

        self.status_icon = None
        self.has_activated = False
        self.notes = []
        self.settings_window = None
        self.keyboard_shortcuts = None
        # There's no use creating the manager if a user is never going to use it, so we don't until it's asked for.
        # Therefore, we should never assume that the manager already exists, and handle the situation gracefully if it
        # is none.
        self.manager = None
        self.notes_hidden = False
        self.autostart_mode = False # indicates if we're in autostart mode

    def do_activate(self):
        if self.has_activated:
            for note in self.notes:
                note.restore()
            self.open_manager()
            return

        Gtk.Application.do_activate(self)

        self.settings = Gio.Settings(schema_id=SCHEMA)

        self.dummy_window = Gtk.Window(title=_("Notes"), default_height=1, default_width=1, decorated=False, deletable=False, name='dummy-window')
        self.dummy_window.show()

        self.file_handler = FileHandler(self.settings, self.dummy_window)

        if self.settings.get_boolean('first-run'):
            self.first_run()

        # Backwards compatibility
        # - Update random color option to cycle
        if self.settings.get_string('default-color') == 'random':
            self.settings.set_string('default-color', 'cycle')

        self.file_handler.connect('lists-changed', self.on_lists_changed)
        self.group_update_id = self.file_handler.connect('group-changed', self.on_group_changed)
        self.file_handler.connect('group-name-changed', self.on_group_name_changed)

        if self.settings.get_boolean('show-in-tray'):
            self.create_status_icon()

        self.settings.connect('changed::show-in-tray', self.update_tray_icon)
        self.settings.connect('changed::show-in-taskbar', self.update_dummy_window)
        self.settings.connect('changed::active-group', self.on_active_group_changed)
        self.update_dummy_window()

        self.note_group = self.settings.get_string('active-group')
        group_names = self.file_handler.get_note_group_names()
        if self.note_group not in group_names:
            if len(group_names) > 0:
                self.note_group = group_names[0]
                self.settings.set_string('active-group', self.note_group)
            else:
                self.file_handler.new_group(self.note_group)

        provider = Gtk.CssProvider()
        provider.load_from_path(STYLE_SHEET_PATH)

        Gtk.StyleContext.add_provider_for_screen (Gdk.Screen.get_default(), provider, 600)

        self.load_notes()

        self.hold()

        if self.autostart_mode:
            self.autostart_mode = False
            if not self.settings.get_boolean("autostart-notes-visible"):
                self.hide_notes()
        else:
            if self.settings.get_boolean("show-manager"):
                self.open_manager()

        if not self.settings.get_boolean("show-in-tray"):
            self.open_manager()

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
                resp = confirm(_("Notes"),
                               _("Would you like to import your notes from Gnote? This will not change your Gnote notes in any way."),
                               window=self.dummy_window)

                if resp:
                    coordinates = 40
                    for file in import_notes:
                        (group_name, info, is_template) = gnote_to_internal_format(file)
                        if not is_template:
                            info['color'] = 'yellow'
                            info['x'] = coordinates
                            info['y'] = coordinates

                            if group_name not in self.file_handler.get_note_group_names():
                                self.file_handler.new_group(group_name)

                            group_list = self.file_handler.get_note_list(group_name)
                            group_list.append(info)
                            self.file_handler.update_note_list(group_list, group_name)

                            coordinates += 20

        # Create a default group
        if len(self.file_handler.get_note_group_names()) == 0:
            self.file_handler.update_note_list([{'text':'', 'color':'yellow', 'x': 20, 'y': 20}], _("Group 1"))

        self.settings.set_boolean('first-run', False)

    def create_status_icon(self):
        self.status_icon = XApp.StatusIcon()
        self.status_icon.set_name('sticky')
        self.status_icon.set_icon_name('sticky-symbolic')
        self.status_icon.set_tooltip_text('%s\n<i>%s</i>\n<i>%s</i>' % (_("Notes"),
                                                                        _("Left click to toggle notes"),
                                                                        _("Middle click to toggle the manager")))
        self.status_icon.set_visible(True)
        self.status_icon.connect('button-press-event', self.on_tray_button_pressed)
        self.status_icon.connect('button-release-event', self.on_tray_button_released)

    def on_tray_button_pressed(self, icon, x, y , button, time, panel_position):
        if button == 1:
            self.activate_notes(time)
        elif button == 2:
            self.toggle_manager(time)

    def on_tray_button_released(self, icon, x, y , button, time, panel_position):
      if button == 3:
            menu = Gtk.Menu()
            item = Gtk.MenuItem(label=_("New Note"))
            item.connect('activate', self.new_note)
            menu.append(item)

            item = Gtk.MenuItem(label=_("Manage Notes"))
            item.connect('activate', self.open_manager)
            menu.append(item)

            menu.append(Gtk.SeparatorMenuItem())

            for group in self.file_handler.get_note_group_names():
                item = Gtk.RadioMenuItem(label=group)
                if group == self.settings.get_string('active-group'):
                    item.set_active(True)
                else:
                    item.connect('activate', self.on_tray_group_selected, group)
                menu.append(item)

            menu.append(Gtk.SeparatorMenuItem())

            item = Gtk.MenuItem(label=_("Quit"))
            item.connect('activate', self.quit_app)
            menu.append(item)

            menu.show_all()
            self.status_icon.popup_menu(menu, x, y, button, time, panel_position)

    def destroy_status_icon(self):
        self.status_icon.set_visible(False)
        self.status_icon = None

    def update_tray_icon(self, *args):
        if self.settings.get_boolean('show-in-tray'):
            self.create_status_icon()
        else:
            self.open_manager()
            self.destroy_status_icon()

    def on_tray_group_selected(self, widget, name):
        self.settings.set_string('active-group', name)

    def on_active_group_changed(self, settings, key):
        self.change_visible_note_group()

    def update_dummy_window(self, *args):
        if self.settings.get_boolean('show-in-taskbar') and not self.notes_hidden:
            self.dummy_window.set_skip_taskbar_hint(False)
        else:
            self.dummy_window.set_skip_taskbar_hint(True)

        self.dummy_window.move(-2, -2)

        if self.settings.get_boolean('desktop-window-state'):
            self.dummy_window.stick()

    def activate_notes(self, time):
        for note in self.notes:
            if note.is_active():
                self.hide_notes()
                return

        self.dummy_window.present_with_time(time)

        for note in self.notes:
            note.restore(time)

        if len(self.notes) == 0:
            self.new_note()

        self.notes_hidden = False
        self.update_dummy_window()

    def hide_notes(self):
        for note in self.notes:
            note.hide()
        
        self.notes_hidden = True
        self.update_dummy_window()

    def new_note(self, *args):
        x = 40
        y = 40
        while(True):
            found = False
            for note_info in self.file_handler.get_note_list(self.note_group):
                if note_info['x'] == x and note_info['y'] == y:
                    found = True
                    break
            if not found:
                break
            x += 20
            y += 20
        info = {'x': x, 'y': y}
        note = self.generate_note(info)
        note.present_with_time(Gtk.get_current_event_time())

        # Note is Gdk.WindowType.UTILITY - these don't get raised automatically
        # (see muffin: window.c:window_state_on_map)
        if not note.get_realized():
            note.realize()
        note.get_window().raise_()

        note.trigger_update()

    def generate_note(self, info={}):
        note = Note(self, self.dummy_window, info)
        note.connect('update', self.on_update)
        note.connect('removed', self.on_removed)

        self.notes.append(note)

        return note

    def load_notes(self):
        for note in self.notes:
            note.destroy()

        self.notes = []

        for note_info in self.file_handler.get_note_list(self.note_group):
            self.generate_note(note_info)

    def focus_note(self, note_info):
        for note in self.notes:
            if note.get_info() == note_info:
                note.present_with_time(0)

    def on_lists_changed(self, *args):
        if not self.note_group in self.file_handler.get_note_group_names():
            self.change_visible_note_group()
        else:
            self.load_notes()

    def on_group_changed(self, f, group_name):
        if self.note_group == group_name:
            self.load_notes()

    def on_group_name_changed(self, f, old_name, new_name):
        if self.note_group == old_name:
            self.change_visible_note_group(new_name)

        if self.settings.get_string('active-group') == old_name:
            self.settings.set_string('active-group', new_name)

    def change_visible_note_group(self, group=None):
        default = self.settings.get_string('active-group')
        if group is None:
            self.note_group = default
        else:
            self.note_group = group

        group_names = self.file_handler.get_note_group_names()
        if self.note_group not in group_names:
            if len(group_names) > 0:
                self.note_group = group_names[0]
            else:
                self.file_handler.new_group(default)
                self.note_group = default

        self.load_notes()

    def open_manager(self, *args, time=0):
        if self.manager:
            if time == 0:
                time = Gtk.get_current_event_time()
            self.manager.window.present_with_time(time)
            return

        self.manager = NotesManager(self, self.file_handler)
        self.manager.window.connect('delete-event', self.manager_closed)

    def toggle_manager(self, time):
        if self.manager and self.manager.window.is_active() and self.manager.window.is_visible():
            self.manager.window.hide()
        else:
            self.open_manager(time=time)

    def manager_closed(self, *args):
        if self.status_icon is None:
            self.quit_app()

        self.manager.window.hide()

        return Gdk.EVENT_STOP

    def open_settings_window(self, *args):
        if self.settings_window:
            self.settings_window.present_with_time(Gtk.get_current_event_time())
            return

        self.settings_window = SettingsWindow(self)
        self.settings_window.connect('destroy', self.settings_window_closed)

        self.settings_window.show_all()

    def open_about(self, widget):
        dlg = Gtk.AboutDialog()
        dlg.set_transient_for(self.manager.window)
        dlg.set_modal(True)
        dlg.set_title(_("About"))
        dlg.set_program_name(_("Notes"))
        dlg.set_comments(_("Take notes and stay organized"))
        try:
            h = open('/usr/share/common-licenses/GPL', encoding="utf-8")
            s = h.readlines()
            gpl = ""
            for line in s:
                gpl += line
            h.close()
            dlg.set_license(gpl)
        except Exception as e:
            print (e)

        dlg.set_version("__DEB_VERSION__")
        dlg.set_icon_name("sticky")
        dlg.set_logo_icon_name("sticky")
        dlg.set_website("https://www.github.com/linuxmint/sticky")
        def close(w, res):
            if res == Gtk.ResponseType.CANCEL or res == Gtk.ResponseType.DELETE_EVENT:
                w.destroy()
        dlg.connect("response", close)
        dlg.show()

    def settings_window_closed(self, *args):
        self.settings_window = None

    def open_keyboard_shortcuts(self, *args):
        if self.keyboard_shortcuts:
            self.keyboard_shortcuts.present_with_time(Gtk.get_current_event_time())
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

if __name__ == "__main__":
    autostart_mode = False
    if "--autostart" in sys.argv:
        settings = Gio.Settings(schema_id=SCHEMA)
        if not settings.get_boolean("autostart"):
            sys.exit()
        else:
            autostart_mode = True

    sticky = Application()
    sticky.autostart_mode = autostart_mode
    sticky.run()
