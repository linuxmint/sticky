#!/usr/bin/python3

from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango
from note_buffer import NoteBuffer
from common import HoverBox, confirm


NOTE_TARGETS = [Gtk.TargetEntry.new('note-entry', Gtk.TargetFlags.SAME_APP, 1)]

class NoteEntry(Gtk.Container):
    initialized = False

    def __init__(self, item):
        super(NoteEntry, self).__init__(height_request=150,
                                        width_request=150,
                                        valign=Gtk.Align.START,
                                        halign=Gtk.Align.CENTER,
                                        margin=10)

        self.item = item

        self.set_has_window(False)

        self.buffer = NoteBuffer()
        self.text = Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR, populate_all=True, buffer=self.buffer, visible=True, sensitive=False)

        self.buffer.set_view(self.text)
        self.buffer.set_from_internal_markup(item.text)

        self.text.set_parent(self)

        self.initialized = True

        self.show_all()

    def do_size_allocate(self, allocation):
        Gtk.Widget.do_size_allocate(self, allocation)

        rect = Gdk.Rectangle()
        rect.x = allocation.x + 10
        rect.y = allocation.y + 10
        rect.width = allocation.width - 20
        rect.height = allocation.height - 20

        self.text.size_allocate(rect)
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
            callback(self.text, *args)

class GroupEntry(Gtk.ListBoxRow):
    def __init__(self, item):
        super(GroupEntry, self).__init__()
        self.item = item
        self.file_handler = self.item.file_handler

        self.hoverbox = HoverBox()
        self.add(self.hoverbox)

        self.menu = Gtk.Menu()

        self.new_item = Gtk.MenuItem(label=_("New"), visible=True)
        self.menu.append(self.new_item)

        self.menu.append(Gtk.SeparatorMenuItem(visible=True))

        item = Gtk.MenuItem(label=_("Edit"), visible=True)
        item.connect('activate', self.edit_group_name)
        self.menu.append(item)

        item = Gtk.MenuItem(label=_("Remove"), visible=True)
        item.connect('activate', self.remove_group)
        self.menu.append(item)

        self.menu.append(Gtk.SeparatorMenuItem(visible=True))

        self.preview_item = Gtk.MenuItem(label=_("Preview"), visible=True)
        self.menu.append(self.preview_item)

        self.default_item = Gtk.MenuItem(label=_("Set as default"), visible=True)
        self.menu.append(self.default_item)

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
        self.box = Gtk.Box(height_request=34)
        self.hoverbox.add(self.box)

        if self.item.is_default:
            self.box.pack_start(Gtk.Image.new_from_icon_name('emblem-default-symbolic', Gtk.IconSize.BUTTON), False, False, 2)
        elif self.item.visible:
            self.box.pack_start(Gtk.Image.new_from_icon_name('group-visible-symbolic', Gtk.IconSize.BUTTON), False, False, 2)
        else:
            self.box.pack_start(Gtk.Box(height_request=16, width_request=16), False, False, 2)

        label = Gtk.Label(label=self.item.name, halign=Gtk.Align.START, margin=5)
        self.box.pack_start(label, True, True, 5)

        image = Gtk.Image.new_from_icon_name('edit', Gtk.IconSize.BUTTON)
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

        self.clean_up(self.entry)

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

class Group(GObject.Object):
    def __init__(self, name, file_handler, model, is_default=False, visible=False):
        super(Group, self).__init__()

        self.is_default = is_default
        self.visible = visible
        self.name = name
        self.file_handler = file_handler
        self.model = model

class Note(GObject.Object):
    def __init__(self, info):
        super(Note, self).__init__()
        self.info = info
        self.text = info['text']
        if info['title'] in [None, '']:
            self.title = _("Untitled")
        else:
            self.title = info['title']

class NotesManager(object):
    def __init__(self, app, file_handler):
        self.app = app
        self.visible_group = None
        self.dragged_note = None

        self.file_handler = file_handler
        self.file_handler.connect('group-changed', self.on_list_changed)
        self.file_handler.connect('lists-changed', self.generate_group_list)

        self.app.connect('visible-group-changed', self.on_visible_group_changed)

        self.builder = Gtk.Builder.new_from_file('/usr/share/sticky/manager.ui')

        self.window = self.builder.get_object('main_window')
        self.group_list = self.builder.get_object('group_list')
        self.note_view = self.builder.get_object('note_view')

        def create_group_entry(item):
            widget = GroupEntry(item)
            widget.drag_dest_set(Gtk.DestDefaults.MOTION | Gtk.DestDefaults.HIGHLIGHT, NOTE_TARGETS, Gdk.DragAction.MOVE)
            widget.connect('drag-drop', self.handle_drop)

            widget.new_item.connect('activate', self.new_group)
            widget.preview_item.connect('activate', lambda *args: self.set_visible_group(item.name))
            widget.default_item.connect('activate', lambda *args: self.set_default(item.name))

            return widget

        self.group_model = Gio.ListStore()
        self.group_list.bind_model(self.group_model, create_group_entry)
        self.group_list.connect('row-selected', self.generate_previews)

        self.builder.get_object('new_note').connect('clicked', self.new_note)
        self.builder.get_object('remove_note').connect('clicked', self.remove_note)
        self.builder.get_object('preview_group').connect('clicked', lambda *args: self.set_visible_group())
        self.builder.get_object('set_default').connect('clicked', lambda *args: self.set_default())

        self.entry_box = self.builder.get_object('group_name_entry_box')
        self.entry_box.drag_dest_set(Gtk.DestDefaults.MOTION | Gtk.DestDefaults.HIGHLIGHT, NOTE_TARGETS, Gdk.DragAction.MOVE)
        self.entry_box.connect('drag-drop', self.handle_new_group_drop)

        main_menu = Gtk.Menu()

        item = Gtk.MenuItem(label=_("New Group"))
        item.connect('activate', self.new_group)
        main_menu.append(item)

        item = Gtk.MenuItem(label=_("Remove Group"))
        item.connect('activate', self.remove_group)
        main_menu.append(item)

        main_menu.append(Gtk.SeparatorMenuItem(visible=True))

        item = Gtk.MenuItem(label=_("Back Up Notes"))
        item.connect('activate', self.file_handler.save_backup)
        main_menu.append(item)

        item = Gtk.MenuItem(label=_("Back Up To File"))
        item.connect('activate', self.file_handler.backup_to_file)
        main_menu.append(item)

        item = Gtk.MenuItem(label=_("Restore Backup"))
        item.connect('activate', self.file_handler.restore_backup)
        main_menu.append(item)

        main_menu.append(Gtk.SeparatorMenuItem(visible=True))

        item = Gtk.MenuItem(label=_("Settings"))
        item.connect('activate', self.app.open_settings_window)
        main_menu.append(item)

        item = Gtk.MenuItem(label=_("Keyboard Shortcuts"))
        item.connect('activate', self.app.open_keyboard_shortcuts)
        main_menu.append(item)

        main_menu.show_all()

        self.builder.get_object('menu_button').set_popup(main_menu)

        self.generate_group_list()

        self.window.show_all()

    def on_list_changed(self, a, group_name):
        if group_name == self.get_current_group():
            self.generate_previews()

    def generate_group_list(self, *args):
        selected_group_name = self.get_current_group()
        self.group_model.remove_all()

        for group_name in self.file_handler.get_note_group_names():
            model = Gio.ListStore()

            is_default = self.app.settings.get_string('default-group') == group_name
            visible = self.visible_group == group_name

            self.group_model.append(Group(group_name, self.file_handler, model, is_default, visible))

        self.group_list.show_all()

        for row in self.group_list.get_children():
            if row.item.name == selected_group_name:
                self.group_list.select_row(row)
                return

    def generate_previews(self, *args):
        selected_row = self.group_list.get_selected_row()
        if selected_row is None:
            return

        group_info = selected_row.item
        group_name = group_info.name
        model = group_info.model

        model.remove_all()

        for note in self.file_handler.get_note_list(group_name):
            model.append(Note(note))

        def create_note_entry(item):
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

            entry = NoteEntry(item)
            wrapper.pack_start(entry, False, False, 0)

            label = Gtk.Label(label=item.title, visible=True)
            outer_box.pack_start(label, False, False, 0)

            widget.show_all()

            return widget

        self.note_view.bind_model(model, create_note_entry)

    def get_current_group(self):
        row = self.group_list.get_selected_row()
        return row.item.name if row is not None else None

    def get_selected_note(self):
        return self.note_view.get_selected_children()[0].item.info

    def set_visible_group(self, group_name=None):
        if group_name is None:
            group_name = self.get_current_group()

        if self.visible_group == group_name:
            return

        self.app.change_visible_note_group(group_name)

    def on_visible_group_changed(self, *args):
        self.visible_group = self.app.note_group
        self.generate_group_list()

    def new_note(self, *args):
        group_name = self.get_current_group()

        self.set_visible_group(group_name)
        self.app.new_note()

    def create_new_group(self, callback):
        entry = Gtk.Entry(visible=True)
        self.entry_box.pack_start(entry, False, False, 5)
        activate_id = 0
        focus_id = 0
        key_id = 0

        def clean_up(entry):
            entry.disconnect(activate_id)
            entry.disconnect(focus_id)

            self.entry_box.remove(entry)

            self.generate_group_list()

        def maybe_done(entry, *args):
            group_name = entry.get_text()
            if group_name == '':
                group_name = None
            else:
                self.file_handler.new_group(group_name)

            clean_up(entry)
            callback(group_name)

        def key_pressed(entry, event):
            if event.keyval != Gdk.KEY_Escape:
                return Gdk.EVENT_PROPAGATE

            clean_up(entry)
            callback(None)

        entry.grab_focus()
        activate_id = entry.connect('activate', maybe_done)
        focus_id = entry.connect('focus-out-event', maybe_done)
        key_id = entry.connect('key-press-event', key_pressed)

    def new_group(self, *args):
        old_group = self.get_current_group()

        def on_complete(group_name):
            if group_name is None:
                group_name = old_group

            for row in self.group_list.get_children():
                if row.item.name == group_name:
                    self.group_list.select_row(row)
                    self.set_visible_group(group_name)

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

    def set_default(self, group_name=None):
        if group_name is None:
            group_name = self.get_current_group()

        self.app.settings.set_string('default-group', group_name)
        self.set_visible_group(group_name)

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

        def on_created(group_name):
            if group_name is None:
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
                    self.set_visible_group(group_name)

                    return

        self.create_new_group(on_created)

        Gtk.drag_finish(context, True, False, time)
