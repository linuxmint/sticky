#!/usr/bin/python3

from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango, XApp
from note_buffer import NoteBuffer
from common import HoverBox
from util import clean_text

NOTE_TARGETS = [Gtk.TargetEntry.new('note-entry', Gtk.TargetFlags.SAME_APP, 1)]

class NoteEntry(Gtk.Container):
    initialized = False

    def __init__(self, item, settings):
        super(NoteEntry, self).__init__(height_request=150,
                                        width_request=150,
                                        valign=Gtk.Align.START,
                                        halign=Gtk.Align.CENTER)

        self.item = item
        self.settings = settings

        self.set_has_window(False)
        self.style_manager = XApp.StyleManager(widget=self)

        self.title_bar = Gtk.Box(name='title-bar', visible=True)
        self.title_bar.pack_start(Gtk.Label(label=item.title, name='title', visible=True, margin_top=5, margin_bottom=5, ellipsize=Pango.EllipsizeMode.END), False, False, 0)
        self.title_bar.set_parent(self)

        self.buffer = NoteBuffer()
        self.text = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, populate_all=True, buffer=self.buffer, visible=True, sensitive=False)
        self.text.set_parent(self)

        self.buffer.set_view(self.text)
        self.buffer.set_from_internal_markup(item.text)

        self.settings.connect('changed::font', self.set_font)
        self.set_font()

        self.set_tooltip_text(item.title)

        self.initialized = True

        self.show_all()

    def do_size_allocate(self, allocation):
        Gtk.Widget.do_size_allocate(self, allocation)

        title_bar_height = self.title_bar.get_preferred_height()[1]

        title_rect = Gdk.Rectangle()
        title_rect.x = allocation.x
        title_rect.y = allocation.y
        title_rect.width = allocation.width
        title_rect.height = title_bar_height
        self.title_bar.size_allocate(title_rect)

        content_rect = Gdk.Rectangle()
        content_rect.x = allocation.x + 10
        content_rect.y = allocation.y + title_bar_height + 10
        content_rect.width = allocation.width - 20
        content_rect.height = allocation.height - title_bar_height - 20
        self.text.size_allocate(content_rect)

        self.set_clip(allocation)

    def do_get_preferred_height(self):
        return (150, 150)

    def do_get_preferred_height_for_width(self, width):
        return (150, 150)

    def do_get_preferred_width(self):
        return (150, 150)

    def do_get_preferred_width_for_height(self, height):
        return (150, 150)

    def do_destroy(self):
        if not self.initialized:
            return

        self.text.unparent()

        self.initialized = False
        Gtk.Container.do_destroy(self)

    def do_forall(self, include_internals, callback, *args):
        if include_internals:
            callback(self.title_bar, *args)
            callback(self.text, *args)

    def set_font(self, *args):
        self.style_manager.set_from_pango_font_string(self.settings.get_string('font'))

class GroupEntry(Gtk.ListBoxRow):
    def __init__(self, item):
        super(GroupEntry, self).__init__()
        self.item = item
        self.file_handler = self.item.file_handler

        self.props.height_request = 35

        self.hoverbox = HoverBox()
        self.add(self.hoverbox)

        self.menu = Gtk.Menu()

        self.new_item = Gtk.MenuItem(label=_("New"), visible=True)
        self.menu.append(self.new_item)

        self.menu.append(Gtk.SeparatorMenuItem(visible=True))

        item = Gtk.MenuItem(label=_("Edit"), visible=True)
        item.connect('activate', self.edit_group_name)
        self.menu.append(item)

        self.remove_item = Gtk.MenuItem(label=_("Remove"), visible=True)
        self.remove_item.connect('activate', self.remove_group)
        self.menu.append(self.remove_item)

        self.connect('popup-menu', self.on_popup)
        self.connect('button-press-event', self.on_button_press)
        self.connect('key-press-event', self.on_key_press)

        self.generate_content()

    def on_popup(self, *args):
        self.menu.popup_at_widget(self, Gdk.Gravity.CENTER, Gdk.Gravity.CENTER, None)

    def on_button_press(self, w, event):
        if event.button == 3:
            self.menu.popup_at_pointer(event)

    def on_key_press(self, w, event):
        if event.keyval == Gdk.KEY_Delete:
            self.remove_group()

            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    def generate_content(self):
        self.box = Gtk.Box()
        self.hoverbox.add(self.box)

        label = Gtk.Label(label=self.item.name, halign=Gtk.Align.START, margin_start=5)
        self.box.pack_start(label, True, True, 5)

        image = Gtk.Image.new_from_icon_name('document-edit-symbolic', Gtk.IconSize.BUTTON)
        button = Gtk.Button(image=image, relief=Gtk.ReliefStyle.NONE, name='manager-group-edit-button')
        self.box.pack_end(button, False, False, 2)
        button.connect('clicked', self.edit_group_name)
        self.hoverbox.set_child_widget(button)

        self.box.show_all()

    def remove_group(self, *args):
        self.file_handler.remove_group(self.item.name)

    def edit_group_name(self, *args):
        self.box.destroy()
        self.box = None

        self.entry = Gtk.Entry(visible=True, text=self.item.name)
        self.hoverbox.add(self.entry)

        self.activate_id = self.entry.connect('activate', self.maybe_done)
        self.focus_id = self.entry.connect('focus-out-event', self.maybe_done)
        self.key_id = self.entry.connect('key-press-event', self.key_pressed)
        self.hoverbox.disable()

        self.entry.grab_focus()

    def maybe_done(self, *args):
        group_name = self.entry.get_text()
        if group_name != '' and group_name != self.item.name:
            old_name = self.item.name
            self.item.name = group_name
            self.file_handler.change_group_name(old_name, group_name)

        self.clean_up()

    def key_pressed(self, w, event):
        if event.keyval != Gdk.KEY_Escape:
            return Gdk.EVENT_PROPAGATE

        self.clean_up()

        return Gdk.EVENT_STOP

    def clean_up(self):
        if self.entry is None:
            return

        self.entry.disconnect(self.activate_id)
        self.entry.disconnect(self.focus_id)
        self.entry.disconnect(self.key_id)

        self.entry.destroy()
        self.entry = None

        self.generate_content()
        self.hoverbox.enable()

    def set_can_remove(self, can_remove):
        self.remove_item.set_sensitive(can_remove)

class Group(GObject.Object):
    def __init__(self, name, file_handler):
        super(Group, self).__init__()
        self.name = name
        self.file_handler = file_handler
        self.model = Gio.ListStore()

        self.update_notes()

    def update_notes(self):
        self.model.remove_all()

        for note in self.file_handler.get_note_list(self.name):
            self.model.append(Note(note, self.name))

class Note(GObject.Object):
    def __init__(self, info, group_name):
        super(Note, self).__init__()
        self.info = info
        self.group_name = group_name
        self.text = info['text']
        if not 'title'in info or info['title'] in [None, '']:
            self.title = _("Untitled")
        else:
            self.title = info['title']

class NotesManager(object):
    def __init__(self, app, file_handler):
        self.app = app
        self.dragged_note = None
        self.search_model = Gio.ListStore()

        self.file_handler = file_handler
        self.file_handler.connect('group-changed', self.on_group_changed)
        self.file_handler.connect('lists-changed', self.refresh_group_list)

        self.builder = Gtk.Builder()
        self.builder.set_translation_domain("sticky")
        self.builder.add_from_file('/usr/share/sticky/manager.ui')

        self.window = self.builder.get_object('main_window')
        self.window.resize(self.app.settings.get_int('manager-width'), self.app.settings.get_int('manager-height'))
        self.window.connect('unrealize', self.cache_window_size)

        self.group_list = self.builder.get_object('group_list')
        self.group_model = Gio.ListStore()
        self.group_list.bind_model(self.group_model, self.create_group_entry)

        self.note_view = self.builder.get_object('note_view')
        self.note_view.connect('child-activated', self.on_note_activated)
        self.note_view.connect('selected-children-changed', self.on_selected_notes_changed)

        self.builder.get_object('new_note').connect('clicked', self.app.new_note)
        self.remove_note_button = self.builder.get_object('remove_note')
        self.remove_note_button.connect('clicked', self.remove_note)
        self.duplicate_note_button = self.builder.get_object('duplicate_note')
        self.duplicate_note_button.connect('clicked', self.duplicate_note)

        # search
        search_toggle = self.builder.get_object('search_toggle_button')
        self.search_bar = self.builder.get_object('search_bar')
        GObject.Object.bind_property(search_toggle, 'active', self.search_bar, 'search_mode_enabled', GObject.BindingFlags.BIDIRECTIONAL)

        self.search_box = self.builder.get_object('search_box')
        self.search_box.connect('search-changed', self.on_search_changed)

        self.entry_box = self.builder.get_object('group_name_entry_box')
        self.entry_box.drag_dest_set(Gtk.DestDefaults.MOTION | Gtk.DestDefaults.HIGHLIGHT, NOTE_TARGETS, Gdk.DragAction.MOVE)
        self.entry_box.connect('drag-drop', self.handle_new_group_drop)


        accel_group = Gtk.AccelGroup()
        self.window.add_accel_group(accel_group)
        key, mod = Gtk.accelerator_parse('<Control>f')
        accel_group.connect(key, mod, Gtk.AccelFlags.VISIBLE, self.open_search)

        # connect main menu signals
        self.builder.get_object('new_menu_item').connect('activate', self.new_group)

        self.remove_group_item = self.builder.get_object('remove_group_menu_item')
        self.remove_group_item.connect('activate', self.remove_group)

        self.builder.get_object('backup_menu_item').connect('activate', self.file_handler.save_backup)
        self.builder.get_object('restore_backup_menu_item').connect('activate', self.file_handler.restore_backup, self.window)
        self.builder.get_object('import_menu_item').connect('activate', self.file_handler.import_notes, self.window)
        self.builder.get_object('export_menu_item').connect('activate', self.file_handler.export_notes, self.window)
        self.builder.get_object('preferences_menu_item').connect('activate', self.app.open_settings_window)
        self.builder.get_object('shortcuts_menu_item').connect('activate', self.app.open_keyboard_shortcuts)
        self.builder.get_object('about_menu_item').connect("activate", self.app.open_about)

        self.refresh_group_list()

        self.window.show_all()

        self.generate_previews()
        self.group_list.connect('row-selected', self.on_group_selected)
        self.group_list.connect('button-press-event', self.on_list_clicked)
        self.app.settings.connect('changed::active-group', self.on_active_group_changed)

    def on_list_clicked(self, list, event):
        for note in self.app.notes:
            note.present_with_time(Gtk.get_current_event_time())

    def on_group_changed(self, a, group_name):
        for group in self.group_model:
            if group.name == group_name:
                group.update_notes()

    def refresh_group_list(self, *args):
        name = None
        selected_group_name = self.get_current_group()
        self.group_model.remove_all()

        for group_name in self.file_handler.get_note_group_names():
            if self.app.settings.get_string('active-group') == group_name:
                name = group_name

            self.group_model.append(Group(group_name, self.file_handler))

        self.group_list.show_all()

        if name != None:
            self.select_group(name)

        children = self.group_list.get_children()
        for item in children:
            item.set_can_remove(len(children) != 1)

        self.remove_group_item.set_sensitive(len(children) != 1)

    def select_group(self, name):
        for row in self.group_list.get_children():
            if row.item.name == name:
                self.group_list.select_row(row)
                break

    def on_active_group_changed(self, settings, key):
        value = settings.get_string(key)
        self.select_group(value)

    def on_group_selected(self, listbox, row):
        group_name = self.get_current_group()
        if group_name != None:
            if self.app.settings.get_string('active-group') != group_name:
                self.app.settings.set_string('active-group', group_name)
            self.generate_previews()

    def on_search_changed(self, *args):
        search_text = self.search_box.get_text().lower().strip()
        if search_text == '':
            self.generate_previews()

        else:
            self.search_model.remove_all()

            for group_name in self.file_handler.get_note_group_names():
                for note_info in self.file_handler.get_note_list(group_name):
                    if note_info['title'].lower().find(search_text) != -1 or clean_text(note_info['text']).find(search_text) != -1:
                        self.search_model.append(Note(note_info, group_name))

            self.note_view.bind_model(self.search_model, self.create_note_entry)

    def open_search(self, *args):
        self.search_bar.set_search_mode(True)

    def on_note_activated(self, *args):
        activated = self.note_view.get_selected_children()[0].item
        activated_group = activated.group_name
        self.select_group(activated_group)

        self.app.focus_note(activated.info)

    def on_selected_notes_changed(self, *args):
        sensitive = len(self.note_view.get_selected_children()) != 0
        self.remove_note_button.set_sensitive(sensitive)
        self.duplicate_note_button.set_sensitive(sensitive)

    def create_group_entry(self, item):
        widget = GroupEntry(item)
        widget.drag_dest_set(Gtk.DestDefaults.MOTION | Gtk.DestDefaults.HIGHLIGHT, GRID_NOTE_TARGETS, Gdk.DragAction.MOVE)
        widget.connect('drag-drop', self.handle_drop)
        widget.new_item.connect('activate', self.new_group)

        return widget

    def create_note_entry(self, item):
        widget = Gtk.FlowBoxChild()
        widget.item = item

        dnd_wrapper = Gtk.EventBox(above_child=True)
        dnd_wrapper.drag_source_set(Gdk.ModifierType.BUTTON1_MASK, NOTE_TARGETS, Gdk.DragAction.MOVE)
        dnd_wrapper.connect('drag-begin', self.on_drag_begin)
        widget.add(dnd_wrapper)

        outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin=10, spacing=10)
        outer_box.set_receives_default(True)
        dnd_wrapper.add(outer_box)

        wrapper = Gtk.Box(halign=Gtk.Align.CENTER)
        context = wrapper.get_style_context()
        context.add_class(item.info['color'])
        context.add_class('note-preview')
        outer_box.pack_start(wrapper, False, False, 0)

        entry = NoteEntry(item, self.app.settings)
        wrapper.pack_start(entry, False, False, 0)

        widget.show_all()

        return widget

    def generate_previews(self, *args):
        selected_row = self.group_list.get_selected_row()
        if selected_row is None:
            return

        group_info = selected_row.item

        self.note_view.bind_model(group_info.model, self.create_note_entry)

    def get_current_group(self):
        row = self.group_list.get_selected_row()
        return row.item.name if row is not None else None

    def get_selected_note(self):
        return self.note_view.get_selected_children()[0].item.info

    def create_new_group(self, callback):
        entry = Gtk.Entry(visible=True)
        self.entry_box.pack_start(entry, False, False, 5)
        activate_id = 0
        focus_id = 0
        key_id = 0

        def clean_up(entry):
            entry.disconnect(activate_id)
            entry.disconnect(focus_id)
            entry.disconnect(key_id)

            self.entry_box.remove(entry)

        def maybe_done(entry, *args):
            group_name = entry.get_text()

            clean_up(entry)

            success = False
            if group_name != '':
                success = self.file_handler.new_group(group_name)

            if success:
                self.refresh_group_list()

            callback(group_name, success)

        def key_pressed(entry, event):
            if event.keyval != Gdk.KEY_Escape:
                return Gdk.EVENT_PROPAGATE

            clean_up(entry)
            callback(None, False)

        entry.grab_focus()
        activate_id = entry.connect('activate', maybe_done)
        focus_id = entry.connect('focus-out-event', maybe_done)
        key_id = entry.connect('key-press-event', key_pressed)

    def new_group(self, *args):
        old_group = self.get_current_group()

        def on_complete(group_name, success):
            if not success:
                group_name = old_group

            for row in self.group_list.get_children():
                if row.item.name == group_name:
                    self.group_list.select_row(row)
                    return

        self.create_new_group(on_complete)

    def remove_note(self, *args):
        notes = []
        selected = self.get_selected_note()
        for child in self.note_view.get_children():
            if child.item.info != selected:
                notes.append(child.item.info)

        self.file_handler.update_note_list(notes, self.get_current_group())

    def remove_group(self, *args):
        group_name = self.get_current_group()

        self.file_handler.remove_group(group_name)

    def duplicate_note(self, *args):
        selected = self.get_selected_note()
        note_info = selected.copy()
        note_info['x'] += 50
        note_info['y'] += 50
        group = self.get_current_group()
        notes = self.file_handler.get_note_list(group)
        notes.append(note_info)
        self.file_handler.update_note_list(notes, group)

    def on_drag_begin(self, widget, *args):
        self.dragged_note = widget.get_parent().item.info

    def handle_drop(self, widget, context, x, y, time):
        new_group = widget.item.name
        new_list = self.file_handler.get_note_list(new_group)
        new_list.append(self.dragged_note)

        old_group = self.get_current_group()
        old_list = self.file_handler.get_note_list(old_group)
        old_list.remove(self.dragged_note)

        self.file_handler.update_note_list(new_list, new_group)
        self.file_handler.update_note_list(old_list, old_group)

        self.dragged_note = None

        Gtk.drag_finish(context, True, False, time)

    def handle_new_group_drop(self, widget, context, x, y, time):
        old_group = self.get_current_group()
        old_list = self.file_handler.get_note_list(old_group)

        def on_created(group_name, success):
            if not success:
                group_name = old_group
            else:
                old_list.remove(self.dragged_note)

                new_list = self.file_handler.get_note_list(group_name)
                new_list.append(self.dragged_note)

                self.file_handler.update_note_list(new_list, group_name)
                self.file_handler.update_note_list(old_list, old_group)

            self.dragged_note = None

            for row in self.group_list.get_children():
                if row.item.name == group_name:
                    self.group_list.select_row(row)
                    return

        self.create_new_group(on_created)

        Gtk.drag_finish(context, True, False, time)

    def cache_window_size(self, *args):
        width, height = self.window.get_size()
        self.app.settings.set_int('manager-width', width)
        self.app.settings.set_int('manager-height', height)
