#!/usr/bin/env python3
import asyncio
import telepot
import yaml
import datetime
import random
import math
import dataset

from . import help, task

def format_seconds_as_mm_ss(seconds):
    return "{}:{:02}".format(
        math.floor(seconds/60.0), math.floor(seconds) % 60)


class Tomato(telepot.helper.ChatHandler):
    def __init__(self, seed_tuple, timeout):
        super(Tomato, self).__init__(seed_tuple, timeout)
        self._current_task = None
        # self.chat_id = seed_tuple[1]['chat']['id']
        print(self.chat_id)
        print(self)
        print(self.__dict__)

    @asyncio.coroutine
    def on_message(self, msg):
        # TODO make sure that thing like /tsq is not matched as /ts
        if "/help" == msg["text"]:
            yield from self.sender.sendMessage(help.text)
    # make this auto start task with set goal
        elif ("/starttaskquick" == msg["text"] or
            "/q" == msg["text"]):
            yield from self.task_begin(msg, delay=10, goal="NOTHING")
        elif ("/starttask" == msg["text"] or
            "/st" == msg["text"]):
            yield from self.task_begin(msg)
        elif ("/timeleft" == msg["text"] or
            "/tl" == msg["text"]):
            yield from self.task_time_left(msg)
        elif ("/canceltask" == msg["text"] or
            "/ct" == msg["text"]):
            yield from self.task_cancel(msg)
        elif ("/displaytask" == msg["text"] or
            "/dt" == msg["text"]):
            yield from self.task_current_goal(msg)
        elif "/compliment" == msg["text"]:
            yield from self.compliment(msg)
        elif ("/tomato" == msg["text"] or
            "/t" == msg["text"]):
            yield from self.sender.sendMessage("I AM A TOMATO!!!")
        elif "/alltasks" == msg["text"]:
            yield from self.send_all_tasks_for_user(msg)
        elif ("/tt" == msg["text"] or
              "/taskstoday" == msg["text"]):
            yield from self.tasks_today_for_user(msg)
        elif("/shortbreak" == msg["text"] or
                 "/sb" == msg["text"]):
            yield from self.break_time(msg, delay=60*5)
        elif("/longbreak" == msg["text"] or
                 "/lb" == msg["text"]):
            yield from self.break_time(msg, delay=60*20)
        elif("/tinybreak" == msg["text"]):
            yield from self.break_time(msg, delay=1)

    @asyncio.coroutine
    def task_current_goal(self, msg):
        try:
            yield from self.sender.sendMessage(self._current_task.goal)
        except AttributeError:
            yield from self.sender.sendMessage("NO GOAL.")

    # TODO get this to confirm task needs cancelling
    @asyncio.coroutine
    def task_cancel(self, msg):
        if self._current_task:
            yield from self.sender.sendMessage("TASK CANCELLED.")
            yield from self._current_task.cancel()
            self._current_task = None
        else:
            yield from self.sender.sendMessage("TASK NOT STARTED.")


    @asyncio.coroutine
    def compliment(self, msg):
        compliments = [
            "YOU ARE NOT A TOMATO.",
            "GOOD JOB.",
            "YOU WORK HARD.",
            "MAYBE YOU FAIL. MAYBE NOT.",
            "I AM CONFUSED.",
            "YOUR COMMAND OF LANGUAGE IS ... EXISTENT.",
            "GO HUMAN GO.",
            "YOUR HAIR IS INTERESTING.",
            "GET BACK TO WORK." if self._current_task else "BREAK OVER.",
            ]
        yield from self.sender.sendMessage(random.choice(compliments))


    def task_time_left(self, msg):
        if self._current_task:
            yield from self.sender.sendMessage(
                "{} LEFT TO ACHIEVE ".format(
                format_seconds_as_mm_ss(
                    self._current_task.time_remaining()))+self._current_task.goal)
        else:
            yield from self.sender.sendMessage(
                "TASK NOT STARTED.")

    @asyncio.coroutine
    def task_end(self, msg):
        yield from self.sender.sendMessage("TASK END!")
        reply_keyboard = {'keyboard': [['Yes', 'No']]}
        yield from self.sender.sendMessage(
            "YOU ACHIEVE "+self._current_task.goal+"?", reply_markup=reply_keyboard)
        try:
            print("Starting to listen...")
            l = self._bot.create_listener()
            l.set_options(timeout=30)
            l.capture(chat__id=self.chat_id)
            answer = yield from l.wait()
            # TODO check the answer is in the affirmative with a reply keyboard
            if answer['text'] == 'Yes':
                self._current_task.complete()
                yield from self.sender.sendMessage("GOOD JOB.", reply_markup={'hide_keyboard':True})
            else:
                yield from self.sender.sendMessage("I HAVE BEEN TOLD NOT TO JUDGE YOU.", reply_markup={'hide_keyboard':True})

        except telepot.helper.WaitTooLong as e:
            yield from self.sender.sendMessage("TOO SLOW.", reply_markup={'hide_keyboard':True})
            raise(e)

        # There is now no current task, let the old one fall into
        # garbage collection and die a natural death
        self._current_task = None

    @asyncio.coroutine
    def request_goal(self, msg):
        yield from self.sender.sendMessage("YOUR GOAL:")
        self.listener.capture(chat__id=self.chat_id)
        self.listener.set_options(timeout=30)
        try:
            current_goal_msg = yield from self.listener.wait()
        except telepot.helper.WaitTooLong as e:
            yield from self.sender.sendMessage("TOO SLOW.")
            raise(e)
        except Exception as e:
            yield from self.sender.sendMessage("MALFUNCTION.")
            raise(e)
        self.listener.set_options(timeout=None)
        current_goal = current_goal_msg["text"].replace("@tomato_task_bot ", "")
        return current_goal

    @asyncio.coroutine
    def break_time(self, msg, delay=60*5):
        """A break function."""
        yield from self.sender.sendMessage("BREAK {:d} MIN STARTED".format(int(delay/60)))
        yield from asyncio.sleep(delay)
        yield from self.sender.sendMessage("BREAK OVER")

    @asyncio.coroutine
    def task_begin(self, msg, delay=60*25, goal=None):
        if goal:
            current_goal = goal
        else:
            current_goal = yield from self.request_goal(msg)

        h = task.Task(
            self.chat_id,
            current_goal,
            lambda: asyncio.async(self.task_end(msg)),
            delay=delay,
        )
        self._current_task = h

        yield from self.sender.sendMessage("TASK BEGIN!")

    @asyncio.coroutine
    def send_all_tasks_for_user(self, msg):
        with dataset.connect("sqlite:///tasks.db") as d:
            all_tasks_for_user = str(list(d['tasks'].find(chat_id=self.chat_id)))
            yield from self.sender.sendMessage(all_tasks_for_user)


    @asyncio.coroutine
    def tasks_today_for_user(self, msg):
        with dataset.connect("sqlite:///tasks.db") as d:
            print(d['tasks'].find(chat_id=self.chat_id))
            for x in d['tasks'].find(chat_id=self.chat_id):
                print(x)
            all_tasks_for_user = [x for x in d['tasks'].find(chat_id=self.chat_id) if x["start_time"] > datetime.datetime.now()-datetime.timedelta(days=1)]
            print("all tasks for user")
            print(all_tasks_for_user)
            if len(all_tasks_for_user) == 0:
                yield from self.sender.sendMessage("No tasks completed today.")
            else:
                string_list = ["Tasks completed today"]
                for x in all_tasks_for_user:
                    print(x)
                    string_list.append("{:%H:%M} {goal}".format(
                    x['start_time'], goal=x['goal']))
                yield from self.sender.sendMessage("\n".join(string_list))
