#!/usr/bin/python3

import os
import json

from gi.repository import GLib, GObject

CONFIG_PATH = os.path.join(GLib.get_user_config_dir(), 'sticky', 'notes.json')
SAVE_DELAY = 1

class FileHandler(GObject.Object):
    @GObject.Signal(flags=GObject.SignalFlags.RUN_LAST, return_type=bool,
                    arg_types=(str,),
                    accumulator=GObject.signal_accumulator_true_handled)
    def group_changed(self, group_name):
        pass

    def __init__(self):
        super(FileHandler, self).__init__()

        self.timer_id = 0
        self.notes_lists = {}

        if not os.path.exists(CONFIG_PATH):
            self.update_note_list([{}], _("Desktop"))
        else:
            self.load_notes()

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
        if self.timer_id > 0:
            GLib.source_remove(self.timer_id)

        self.timer_id = GLib.timeout_add_seconds(SAVE_DELAY, self.save_note_list)

    def save_note_list(self):
        self.timer_id = 0

        if not os.path.exists(os.path.dirname(CONFIG_PATH)):
            os.makedirs(os.path.dirname(CONFIG_PATH))

        with open(CONFIG_PATH, 'w+') as file:
            file.write(json.dumps(self.notes_lists, indent=4))

    def remove_group(self, group_name):
        if group_name not in self.notes_lists:
            raise ValueError('invalid group name %s' % group_name)
        del self.notes_lists[group_name]

        self.queue_save()
