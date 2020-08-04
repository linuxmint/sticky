#!/usr/bin/python3

import os
import json
import time
import re

from gi.repository import GLib, GObject

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

    def save_note_list(self):
        self.save_timer_id = 0

        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR)

        with open(CONFIG_PATH, 'w+') as file:
            file.write(json.dumps(self.notes_lists, indent=4))

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
        with open(path, 'w+') as file:
            file.write(json.dumps(self.notes_lists, indent=4))

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

    def flush(self):
        if self.save_timer_id > 0:
            GLib.source_remove(self.save_timer_id)

        self.save_note_list()

    def remove_group(self, group_name):
        if group_name not in self.notes_lists:
            raise ValueError('invalid group name %s' % group_name)
        del self.notes_lists[group_name]

        self.save_note_list()
