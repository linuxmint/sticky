#!/usr/bin/python3

import os
import json
import time
import re

from gi.repository import GLib, GObject, Gtk

CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), 'sticky')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'notes.json')
SAVE_DELAY = 3

backup_file_name = re.compile(r"\Abackup-[0-9]{10,}\.json$", re.IGNORECASE)

class FileHandler(GObject.Object):
    @GObject.Signal(flags=GObject.SignalFlags.RUN_LAST, return_type=bool,
                    arg_types=(str,),
                    accumulator=GObject.signal_accumulator_true_handled)
    def group_changed(self, group_name):
        pass

    @GObject.Signal(flags=GObject.SignalFlags.RUN_LAST, return_type=bool,
                    accumulator=GObject.signal_accumulator_true_handled)
    def lists_changed(self):
        pass

    def __init__(self, settings):
        super(FileHandler, self).__init__()

        self.settings = settings
        self.save_timer_id = 0
        self.backup_timer_id = 0
        self.notes_lists = {}

        if not os.path.exists(CONFIG_PATH):
            self.update_note_list([{}], _("Desktop"))
        else:
            self.load_notes()

        self.settings.connect('changed::automatic-backups', self.check_backup)
        self.settings.connect('changed::backup-interval', self.check_backup)
        self.check_backup()

    def load_notes(self, *args):
        with open(CONFIG_PATH, 'r') as file:
            info = json.loads(file.read())

        self.notes_lists = info

    def get_note_list(self, group_name):
        return self.notes_lists[group_name]

    def get_note_group_names(self):
        return self.notes_lists.keys()

    def update_note_list(self, notes_list, group_name):
        self.notes_lists[group_name] = notes_list

        self.queue_save()

        self.emit('group-changed', group_name)

    def queue_save(self):
        if self.save_timer_id > 0:
            GLib.source_remove(self.save_timer_id)

        self.save_timer_id = GLib.timeout_add_seconds(SAVE_DELAY, self.save_note_list)

    def save_to_file(self, file_path):
        with open(file_path, 'w+') as file:
            file.write(json.dumps(self.notes_lists, indent=4))

    def save_note_list(self):
        self.save_timer_id = 0

        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR)

        self.save_to_file(CONFIG_PATH)

    def check_backup(self, *args):
        if self.backup_timer_id:
            GLib.source_remove(self.backup_timer_id)
            self.backup_timer_id = 0

        if not self.settings.get_boolean('automatic-backups'):
            return

        now = int(time.time())
        last_backup = self.settings.get_uint('latest-backup')
        interval = self.settings.get_uint('backup-interval')

        if last_backup == 0:
            # unless it was reset, this means the application was just started for the first time, so there's no point
            # in running a backup yet
            self.settings.set_uint('latest-backup', now)
            last_backup = now

        next_backup = last_backup + (interval * 3600)

        if next_backup < now:
            self.save_backup()
        else:
            self.backup_timer_id = GLib.timeout_add_seconds(next_backup - now, self.save_backup)

    def save_backup(self, *args):
        self.backup_timer_id = 0

        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR)

        timestamp = int(time.time())
        path = os.path.join(CONFIG_DIR, 'backup-%d.json' % timestamp)
        self.save_to_file(path)

        self.settings.set_uint('latest-backup', timestamp)

        # remove old backups (if applicable)
        backups_keep = self.settings.get_uint('old-backups-max')
        if backups_keep > 0:
            backups = []
            for file in os.listdir(CONFIG_DIR):
                if backup_file_name.search(file):
                    backups.append(file)

            backups.sort()
            for file in backups[0:-backups_keep]:
                os.remove(os.path.join(CONFIG_DIR, file))

        self.check_backup()

    def backup_to_file(self, *args):
        file_dialog = Gtk.FileChooserDialog(title=_("Save Backup"), action=Gtk.FileChooserAction.SAVE)
        file_dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK)
        file_dialog.set_current_folder(GLib.get_home_dir())
        file_dialog.set_current_name('backup.json')
        file_dialog.set_do_overwrite_confirmation(True)

        json_filter = Gtk.FileFilter()
        json_filter.set_name('JSON')
        json_filter.add_mime_type('application/json')
        file_dialog.add_filter(json_filter)

        text_filter = Gtk.FileFilter()
        text_filter.set_name(_("Plain Text"))
        text_filter.add_mime_type('text/plain')
        file_dialog.add_filter(text_filter)

        response = file_dialog.run()
        if response == Gtk.ResponseType.OK:
            file = file_dialog.get_filename()
            self.save_to_file(file)

        file_dialog.destroy()

    def restore_backup(self, *args):
        dialog = Gtk.Dialog(title=_("Restore Backup"))
        dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        dialog.add_button(_("From File"), 20)
        restore_button = dialog.add_button(_("Restore"), Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)

        content = dialog.get_content_area()

        backup_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.BROWSE)
        content.pack_start(backup_list, True, True, 0)

        backups = []
        for file in os.listdir(CONFIG_DIR):
            if backup_file_name.search(file):
                backups.append(file)

        backups.sort()

        if len(backups) == 0:
            restore_button.set_sensitive(False)

        for file_name in backups:
            date = time.localtime(int(file_name[7:-5]))
            label = Gtk.Label(label=time.strftime('%c', date), margin=5)
            label.file = file_name
            backup_list.add(label)

        backup_list.show_all()

        file_path = None
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            file_path = os.path.join(CONFIG_DIR, backup_list.get_selected_row().get_child().file)
        elif response == 20:
            file_dialog = Gtk.FileChooserDialog(title=_("Save Backup"), action=Gtk.FileChooserAction.OPEN)
            file_dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
            file_dialog.set_current_folder(GLib.get_home_dir())

            json_filter = Gtk.FileFilter()
            json_filter.set_name('JSON')
            json_filter.add_mime_type('application/json')
            file_dialog.add_filter(json_filter)

            text_filter = Gtk.FileFilter()
            text_filter.set_name(_("Plain Text"))
            text_filter.add_mime_type('text/plain')
            file_dialog.add_filter(text_filter)

            response = file_dialog.run()
            if response == Gtk.ResponseType.OK:
                file_path = file_dialog.get_filename()

            file_dialog.destroy()

        if file_path is not None:
            try:
                with open(file_path, 'r') as file:
                    info = json.loads(file.read())

                # todo: needs validation here to ensure the file type is correct, and while we're at it, the validation
                # should really be added to load_notes() as well

                self.notes_lists = info
                self.save_note_list()

                self.emit('lists-changed')
            except Exception as e:
                message = Gtk.MessageDialog(text=_("Unable to restore: invalid or corrupted backup file"), buttons=Gtk.ButtonsType.CLOSE)
                message.run()
                message.destroy()

        dialog.destroy()

    def flush(self):
        if self.save_timer_id > 0:
            GLib.source_remove(self.save_timer_id)

        self.save_note_list()

    def remove_group(self, group_name):
        if group_name not in self.notes_lists:
            raise ValueError('invalid group name %s' % group_name)
        del self.notes_lists[group_name]

        self.save_note_list()

def prompt(title, message):
    dialog = Gtk.Dialog(title=title)
    dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
    dialog.add_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
    dialog.set_default_response(Gtk.ResponseType.OK)

    content = dialog.get_content_area()
    content.props.margin_left = 20
    content.props.margin_right = 20

    content.pack_start(Gtk.Label(label=message), False, False, 10)
    entry = Gtk.Entry(activates_default=True)
    content.pack_start(entry, False, False, 10)

    content.show_all()

    response = dialog.run()
    value = entry.get_text()

    dialog.destroy()

    return (response == Gtk.ResponseType.OK, value)

