#!/usr/bin/python3

from gi.repository import Gdk, GObject, Gtk


class GenericAction(object):
    def maybe_join(self, new_action):
        return False

# Used whenever plain text is added to the buffer. Internal characters such as anchor points should be handled with
# ObjectInsertAction, etc.
class AdditionAction(GenericAction):
    def __init__(self, buffer, text, location):
        super(AdditionAction, self).__init__()
        self.buffer = buffer
        self.text = text

        self.position = location.get_offset()

    def undo(self):
        start = self.buffer.get_iter_at_offset(self.position)
        end = self.buffer.get_iter_at_offset(self.position + len(self.text))
        self.buffer.delete(start, end)

    def redo(self):
        self.buffer.insert(self.buffer.get_iter_at_offset(self.position), self.text)

    def maybe_join(self, new_action):
        if not isinstance(new_action, AdditionAction):
            return False

        if new_action.position == self.position + len(self.text):
            self.text += new_action.text
            return True

        return False

# Used whenever text is removed from the buffer.
class DeletionAction(GenericAction):
    # fixme: need to handle object removal somehow
    def __init__(self, buffer, start, end):
        super(DeletionAction, self).__init__()
        self.buffer = buffer
        self.text = buffer.get_slice(start, end, True)

        self.position = start.get_offset()

        if buffer.get_has_selection():
            (buffer_start, buffer_end) = buffer.get_selection_bounds()
            if buffer_start.compare(start) == 0 and buffer_end.compare(end):
                self.deletion_type = 'selection'
            else:
                self.deletion_type = 'other'
        elif self.buffer.get_iter_at_mark(self.buffer.get_insert()).compare(end) == 0:
            self.deletion_type = 'backward'
        elif self.buffer.get_iter_at_mark(self.buffer.get_insert()).compare(start) == 0:
            self.deletion_type = 'foreward'
        else:
            self.deletion_type = 'other'

    def undo(self):
        self.buffer.insert(self.buffer.get_iter_at_offset(self.position), self.text)

    def redo(self):
        start = self.buffer.get_iter_at_offset(self.position)
        end = self.buffer.get_iter_at_offset(self.position + len(self.text))
        self.buffer.delete(start, end)

    def maybe_join(self, new_action):
        if not isinstance(new_action, DeletionAction) or new_action.deletion_type != self.deletion_type:
            return False

        if self.deletion_type == 'foreward' and new_action.position == self.position:
            self.text += new_action.text
            return True
        elif self.deletion_type == 'backward' and new_action.position == self.position - 1:
            self.text = new_action.text + self.text
            self.position = new_action.position
            return True

        return False

# Used for objects inserted at an anchor point such as checkbuttons, bullets, etc.
class ObjectInsertAction(GenericAction):
    def __init__(self, buffer, location, anchor):
        super(ObjectInsertAction, self).__init__()
        self.buffer = buffer
        self.anchor = anchor

        self.position = buffer.get_iter_at_child_anchor(anchor).get_offset()
        # print()
        # print(self.position)

    def undo(self):
        # needs some work
        # print(self.buffer.get_slice(self.buffer.get_iter_at_offset(self.position), self.buffer.get_iter_at_offset(self.position+1), True))
        start_anchor_iter = self.buffer.get_iter_at_offset(self.position)
        end_anchor_iter = self.buffer.get_iter_at_offset(self.position + 1)
        self.checked = start_anchor_iter.get_child_anchor().get_widgets()[0].get_active()
        self.buffer.delete(start_anchor_iter, end_anchor_iter)

    def redo(self):
        # needs some work
        self.buffer.add_check_button(self.buffer.get_iter_at_offset(self.position), self.checked)

# Used for setting formatting tags
class TagAction(GenericAction):
    def __init__(self, buffer, name, start, end):
        super(TagAction, self).__init__()
        self.buffer = buffer
        self.name = name
        self.start = start.get_offset()
        self.end = end.get_offset()

    def undo(self):
        self.buffer.remove_tag_by_name(self.name, self.buffer.get_iter_at_offset(self.start), self.buffer.get_iter_at_offset(self.end))

    def redo(self):
        self.buffer.apply_tag_by_name(self.name, self.buffer.get_iter_at_offset(self.start), self.buffer.get_iter_at_offset(self.end))

# Used to combine multiple actions into one single undable action. Actions should be passed in the same order in which
# they were performed. Failure to do so could result in order getting mixed up in the buffer.
class CompositeAction(GenericAction):
    def __init__(self, *args):
        super(CompositeAction, self).__init__()
        self.child_actions = args

    def undo(self):
        for action in reversed(self.child_actions):
            action.undo()

    def redo(self):
        for action in self.child_actions:
            action.redo()

class NoteBuffer(Gtk.TextBuffer):
    # These values should not be modified directly.
    # inhibit_notify keeps the "content-changed" signal from firing while the buffer performs several actions. It
    # should not be modified directly. Instead use
    #       with self.internal_action():
    #           do_something()
    inhibit_notify = 0

    # in_composite and composite_actions will rarely be used in practice as it is generally much easier and
    # straightforward to construct the composite action directly as you perform them. This functionality is primarily
    # only for functions internal to the view and buffer.
    in_composite = 0
    composite_actions = []

    # used to keep track of undo and redo actions. Use self.add_undo_action() when creating a new action
    undo_actions = []
    redo_actions = []

    @GObject.Property
    def can_undo(self):
        return len(self.undo_actions)

    @GObject.Property
    def can_redo(self):
        return len(self.redo_actions)

    @GObject.Signal(flags=GObject.SignalFlags.RUN_LAST, return_type=bool,
                    accumulator=GObject.signal_accumulator_true_handled)
    def content_changed(self):
        pass

    def __init__(self):
        super(NoteBuffer, self).__init__()

        self.connect('insert-text', self.on_insert)
        self.connect('delete-range', self.on_delete)
        self.connect('begin-user-action', self.begin_composite_action)
        self.connect('end-user-action', self.end_composite_action)

    def trigger_changed(self, *args):
        if not self.inhibit_notify:
            self.emit('content_changed')

    def internal_action(self, trigger_on_complete=True):
        class InternalActionHandler(object):
            def __enter__(a):
                self.inhibit_notify += 1

            def __exit__(a, exc_type, exc_value, traceback):
                self.inhibit_notify -= 1
                if trigger_on_complete:
                    self.trigger_changed()

        return InternalActionHandler()

    def get_internal_markup(self):
        (start, end) = self.get_bounds()
        raw_text = self.get_slice(start, end, True)

        inserted_objects = []
        current_tags = []
        text = ''

        index = 0

        while True:
            index = raw_text.find('\ufffc', index+1)
            if index == -1:
                break

            inserted_objects.append(self.get_iter_at_offset(index))

        # current_iter: our placeholder for where we start copying from
        # current_insert: the next occurrence of an inserted object (bullet, checkbox, etc)
        # next_iter: where we find the next set of tag open/close in the buffer
        current_iter = start.copy()
        current_insert = inserted_objects.pop(0) if len(inserted_objects) > 0 else end
        while True:
            next_iter = current_iter.copy()
            next_iter.forward_to_tag_toggle()

            # if there happens to be an inserted object before the next tag, we handle that first, but otherwise we
            # want to close out our tags first, though it probably doesn't matter since the check boxes are affected
            # by the formatting and vice-versa
            if current_insert.compare(next_iter) < 0:
                text += self.get_slice(current_iter, current_insert, False).replace('#', '##')

                try:
                    checked = current_insert.get_child_anchor().get_widgets()[0].get_active()
                    text += '#check:' + str(int(checked))
                except:
                    pass

                current_iter = current_insert.copy()
                current_iter.forward_char()
                current_insert = inserted_objects.pop(0) if len(inserted_objects) > 0 else end

            else:
                text += self.get_slice(current_iter, next_iter, False).replace('#', '##')

                # if not all tags are closed, we still need to keep track of them, but leaving them in the list will
                # cause an infinite loop, so we hold on to them in unclosed_tags and re-add them after exiting the loop
                unclosed_tags = []

                tags = next_iter.get_toggled_tags(False)
                while len(current_tags) and len(tags):
                    tag = current_tags.pop()

                    if len(tags) == 0 or tag not in tags:
                        unclosed_tags.append(tag)
                        continue

                    text += '#tag:%s:' % tag.props.name
                    tags.remove(tag)

                current_tags += unclosed_tags

                tags = next_iter.get_toggled_tags(True)
                while len(tags):
                    tag = tags.pop()
                    name = tag.props.name

                    text += '#tag:%s:' % tag.props.name
                    current_tags.append(tag)

                current_iter = next_iter

            if current_iter.compare(end) == 0:
                break

        return text

    def set_from_internal_markup(self, text):
        with self.internal_action(False):
            self.set_text('')

            current_index = 0
            open_tags = {}
            while True:
                next_index = text.find('#', current_index)
                if next_index == -1:
                    self.insert(self.get_end_iter(), text[current_index:])
                    break

                self.insert(self.get_end_iter(), text[current_index:next_index])

                if text[next_index:next_index+2] == '##':
                    self.insert(self.get_end_iter(), '#')
                    current_index = next_index + 2
                elif text[next_index:next_index+6] == '#check':
                    checked = bool(int(text[next_index+7]))
                    self.add_check_button(self.get_end_iter(), checked=checked)
                    current_index = next_index + 8
                elif text[next_index:next_index+4] == '#tag':
                    end_tag_index = text.find(':', next_index+6)
                    tag_name = text[next_index+5:end_tag_index]

                    if tag_name in open_tags:
                        mark = open_tags.pop(tag_name)
                        start = self.get_iter_at_mark(mark)
                        end = self.get_end_iter()
                        self.apply_tag_by_name(tag_name, start, end)
                        self.delete_mark(mark)
                    else:
                        open_tags[tag_name] = self.create_mark(None, self.get_end_iter(), True)

                    current_index = next_index + 6 + len(tag_name)

    def undo(self, *args):
        if len(self.undo_actions) == 0:
            print('warning: attempting to undo action when there is nothing to undo')
            return

        with self.internal_action():
            action = self.undo_actions.pop()
            action.undo()
            self.redo_actions.append(action)

    def redo(self, *args):
        if len(self.redo_actions) == 0:
            print('warning: attempting to redo action when there is nothing to redo')
            return

        with self.internal_action():
            action = self.redo_actions.pop()
            action.redo()
            self.undo_actions.append(action)

    def begin_composite_action(self, *args):
        self.in_composite += 1

    def end_composite_action(self, *args):
        self.in_composite -= 1

        # if there are no actions that happen during the composite, there's nothing we need to do
        if self.in_composite or len(self.composite_actions) == 0:
            return

        # some times we get actions tagged as composite when they really shouldn't be, so if there's just one action
        # we don't want to put it inside a composite action as that will break joining actions if applicable
        if len(self.composite_actions) == 1:
            self.add_undo_action(self.composite_actions[0])
        else:
            self.add_undo_action(CompositeAction(*self.composite_actions))

        self.composite_actions.clear()

    def add_undo_action(self, action):
        if self.in_composite:
            self.composite_actions.append(action)
        else:
            self.undo_actions.append(action)
            self.redo_actions.clear()

    def on_insert(self, buffer, location, text, *args):
        if self.inhibit_notify:
            return

        action = AdditionAction(self, text, location)
        if text == '\n' and self.maybe_repeat(location, action):
            return

        if self.props.can_undo:
            self.undo_actions[-1].maybe_join(action)
            return

        self.add_undo_action(action)

    def on_delete(self, buffer, start, end):
        if self.inhibit_notify:
            return

        action = DeletionAction(self, start, end)
        if self.props.can_undo:
            self.undo_actions[-1].maybe_join(action)
            return

        self.add_undo_action(action)

    def tag_selection(self, tag_name):
        if self.get_has_selection():
            self.add_tag(tag_name, *self.get_selection_bounds())
        else:
            self.add_tag(tag_name, self.get_insert(), self.get_insert())

    def add_tag(self, tag_name, start, end):
        self.apply_tag_by_name(tag_name, start, end)
        self.add_undo_action(TagAction(self, tag_name, start, end))

    def add_check_button(self, a_iter, checked=False):
        with self.internal_action():
            anchor = self.create_child_anchor(a_iter)
            check_button = Gtk.CheckButton(visible=True, active=checked, margin_right=5, margin_top=5)
            check_button.connect('toggled', self.trigger_changed)
            self.view.add_child_at_anchor(check_button, anchor)

            return ObjectInsertAction(self, a_iter, anchor)

    def add_bullet(self, a_iter):
        with self.internal_action():
            anchor = self.create_child_anchor(a_iter)
            bullet = Gtk.Image(visible=True, icon_name='menu-bullet', pixel_size=16)
            self.view.add_child_at_anchor(bullet, anchor)

            return ObjectInsertAction(self, a_iter, anchor)

    def toggle_checklist(self, *args):
        actions = []
        with self.internal_action():
            if self.get_has_selection():
                (start, end) = self.get_selection_bounds()
            else:
                start = end = self.get_iter_at_mark(self.get_insert())

            line_index_start = start.get_line()
            line_index_end = end.get_line()

            all_have_checkboxes = True
            for line in range(line_index_start, line_index_end + 1):
                if self.get_iter_at_line(line).get_child_anchor() is None:
                    all_have_checkboxes = False
                    break

            for line in range(line_index_start, line_index_end + 1):
                if all_have_checkboxes:
                    anchor = self.get_iter_at_line(line).get_child_anchor()
                    if anchor is not None:
                        self.view.remove(anchor.get_widgets()[0])
                else:
                    actions.append(self.add_check_button(self.get_iter_at_line(line)))

        if len(actions):
            self.add_undo_action(CompositeAction(*actions))

    def toggle_bullets(self, *args):
        actions = []
        with self.internal_action():
            if self.get_has_selection():
                (start, end) = self.get_selection_bounds()
            else:
                start = end = self.get_iter_at_mark(self.get_insert())

            line_index_start = start.get_line()
            line_index_end = end.get_line()

            all_have_bullets = True
            for line in range(line_index_start, line_index_end + 1):
                if self.get_iter_at_line(line).get_child_anchor() is None:
                    all_have_bullets = False
                    break

            for line in range(line_index_start, line_index_end + 1):
                if all_have_bullets:
                    anchor = self.get_iter_at_line(line).get_child_anchor()
                    if anchor is not None:
                        self.view.remove(anchor.get_widgets()[0])
                else:
                    actions.append(self.add_bullet(self.get_iter_at_line(line)))

        if len(actions):
            self.add_undo_action(CompositeAction(*actions))

    def maybe_repeat(self, current_iter, prev_action):
        line_start = current_iter.copy()
        line_start.set_line_index(0)
        anchor = line_start.get_child_anchor()

        if anchor is None:
            return False

        offset = current_iter.get_offset()
        if isinstance(anchor.get_widgets()[0], Gtk.CheckButton):
            action = self.add_check_button(current_iter)
        if isinstance(anchor.get_widgets()[0], Gtk.Image):
            action = self.add_bullet(current_iter)
        self.add_undo_action(CompositeAction(prev_action, action))

        current_iter.assign(self.get_iter_at_offset(offset))

        return True
