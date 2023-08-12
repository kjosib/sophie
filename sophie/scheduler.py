"""
This is the simple task-queue version of a scheduler.
At some point I may do a work-stealing version for fun,
but the semantics of the language are the same regardless.
"""
import traceback
from collections import deque
from threading import Lock, Thread
from typing import Optional

POOL_SIZE = 3
ALL_DONE = object()

class ThreadPoolScheduler:
	"""
	Responsible for the main task queue and pool of worker threads.
	Can also trigger shut-down. System threads can influence that by
	adjusting the number of busy threads via the pin and unpin methods.
	"""

	def __init__(self, nr_workers:int):
		self.main_thread = DedicatedThread()
		self._mutex = Lock()
		self._tasks = deque()
		self._idle = deque()
		self._nr_busy = nr_workers
		for i in range(nr_workers):
			Thread(target=self._worker, daemon=True, name="worker thread " + str(i)).start()
		# The first thing all those worker-threads will do is become idle,
		# which will result in an "all-done" message to the main thread queue.
		# So we must wait for it.
		self.await_completion()
		
	def await_completion(self):
		self.main_thread.run()
	
	def perform(self, task):
		""" The main thread should call this to kick off a job. """
		self.insert_task(task)
		self.await_completion()

	def insert_task(self, task):
		self._mutex.acquire()
		self._tasks.append(task)
		if self._idle:
			# Let's wake workers LIFO rather than round-robin:
			self._idle.pop().release()
		self._mutex.release()

	def _worker(self):
		notify_me = Lock()
		notify_me.acquire()
		while True:
			self._mutex.acquire()
			while not self._tasks:
				self._idle.append(notify_me)
				self._less_busy()
				self._mutex.release()
				notify_me.acquire()
				self._mutex.acquire()
				self._more_busy()
			task = self._tasks.popleft()
			self._mutex.release()
			try: task.proceed()
			except: traceback.print_exc()
	
	def _less_busy(self):
		self._nr_busy -= 1
		if not self._nr_busy:
			self._all_idle()
	
	def _all_idle(self):
		self.main_thread.insert_task(ALL_DONE)
		#self._all_done.release()

	def _more_busy(self):
		self._nr_busy += 1

	def pin(self):
		"""
		Add one to the busy-thread count, thus preventing shut-down.
		For use by system-threads with pinned actors.
		"""
		with self._mutex:
			self._more_busy()
	
	def unpin(self):
		"""
		Subtract one from the busy-thread count, thus allowing shut-down.
		For use by system-threads with pinned actors.
		"""
		with self._mutex:
			self._less_busy()

class DedicatedThread:
	"""
	Certain things need to consistently run in the same thread.
	The simple way to make sure of that is to dedicate a thread thereto.
	"""
	_tasks : Optional[list]
	
	def __init__(self):
		self._mutex = Lock()
		self._tasks = None
		self._ready = Lock()
		self._ready.acquire()
	
	def start(self):
		Thread(target=self.run, daemon=True).start()

	def run(self):
		while True:
			self._ready.acquire()
			self._mutex.acquire()
			tasks = self._tasks
			self._tasks = None
			self._mutex.release()
			for task in tasks:
				if task is ALL_DONE:
					return
				else:
					task.proceed()
			MAIN_QUEUE.unpin()

	def insert_task(self, task):
		self._mutex.acquire()
		if self._tasks:
			self._tasks.append(task)
		else:
			if task is not ALL_DONE:
				MAIN_QUEUE.pin()
			self._tasks = [task]
			self._ready.release()
		self._mutex.release()

MAIN_QUEUE = ThreadPoolScheduler(POOL_SIZE)

class Task:
	def proceed(self):
		raise NotImplementedError(type(self))

class Actor(Task):
	"""
	Subtlety:
	An actor is a task. A message is *not* a task.
	
	Pin an actor to an alternative queue by
	setting its instance attribute "TASK_QUEUE".
	The turtle-graphics / tkinter actor must use
	this to stay on the main thread.
	"""
	
	TASK_QUEUE = MAIN_QUEUE
	
	_mailbox : Optional[list]
	def __init__(self):
		self._mutex = Lock()  # Protects the mailbox for this actor
		self._mailbox = None
	
	def batch_of_messages(self):
		# Atomically harvest a batch of queued-up messages,
		# thus to minimize the time and frequency of holding the mutex:
		self._mutex.acquire()
		mailbox = self._mailbox
		self._mailbox = None
		self._mutex.release()
		return mailbox
	
	def proceed(self):
		for message in self.batch_of_messages():
			self.handle(*message)
	
	def accept_message(self, method_name, args):
		self._mutex.acquire()
		if self._mailbox is None:
			self._mailbox = []
			self.TASK_QUEUE.insert_task(self)
		self._mailbox.append((method_name, args))
		self._mutex.release()
	
	def handle(self, message, args):
		raise NotImplementedError(type(self))

class NativeObjectProxy(Actor):
	""" Wrap Python objects in one of these to use them as agents. """
	def __init__(self, principal, pin=False):
		super().__init__()
		self._principal = principal
		if pin:
			self.TASK_QUEUE = DedicatedThread()
	def handle(self, method_name, args):
		method = getattr(self._principal, method_name)
		method(*args)


class SampleTask(Task):
	def proceed(self):
		print("Hello, Threading World!")

if __name__ == '__main__':
	MAIN_QUEUE.perform(SampleTask())

