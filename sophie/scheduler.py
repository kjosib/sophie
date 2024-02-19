"""
This is the simple task-queue version of a scheduler.
At some point I may do a work-stealing version for fun,
but the semantics of the language are the same regardless.
"""
from collections import deque
from threading import Lock, Thread
from typing import Optional

POOL_SIZE = 3

class ThreadPoolScheduler:
	"""
	Responsible for the main task queue and pool of worker threads.
	Can also trigger shut-down. System threads can influence that by
	adjusting the number of busy threads via the pin and unpin methods.
	"""

	def __init__(self, nr_workers:int):
		self.main_thread = MainThread(self)
		self._is_shutting_down = False
		self._mutex = Lock()
		self._tasks = deque()
		self._idle = deque()
		self._all_done = Lock()
		self._all_done.acquire()
		self._nr_busy = nr_workers
		for i in range(nr_workers):
			Thread(target=self._worker, args=[i], daemon=True, name="worker thread " + str(i)).start()
		# The first thing all those worker-threads will do is become idle,
		# which will result in an "all-done" message to the main thread queue.
		# So we must wait for it.
		try: self.main_thread.run()
		finally: self._finish_up()
		
	def execute(self, task:"Task"):
		""" The main thread should call this to kick off a job. """
		assert isinstance(task, Task)
		self._is_shutting_down = False
		assert self._all_done.locked()
		task.enqueue()
		try: self.main_thread.run()
		finally: self._finish_up()
		
	def _finish_up(self):
		self._all_done.acquire()
		self._tasks.clear()
		self.main_thread.recover()

	def insert_task(self, task):
		self._mutex.acquire()
		self._tasks.append(task)
		if self._idle:
			# Let's wake workers LIFO rather than round-robin:
			self._more_busy()
			self._idle.pop().release()
		self._mutex.release()

	def _worker(self, i):
		notify_me = Lock()
		notify_me.acquire()
		while True:
			self._mutex.acquire()
			while self._is_shutting_down or not self._tasks:
				self._idle.append(notify_me)
				self._less_busy()
				self._mutex.release()
				notify_me.acquire()
				self._mutex.acquire()
			task = self._tasks.popleft()
			self._mutex.release()
			try: task.proceed()
			except BaseException as ex:
				self.main_thread.insert_task(ex)
	
	def _less_busy(self):
		# Precondition: self.mutex is held
		self._nr_busy -= 1
		if 0 == self._nr_busy and not self._is_shutting_down:
			self._is_shutting_down = True
			self.main_thread.stop()
			self._all_done.release()
	
	def _more_busy(self):
		# Precondition: self.mutex is held
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

class MainThread:
	"""
	The main thread starts and stops the thread pool,
	and also propagates exceptions outward.
	As such, its run loop is a bit different.
	
	Also, certain things need to run from the main thread (e.g. Turtle Graphics)
	or at least consistently in the same thread. The simple way to make sure of
	that is to run all such picky things on the main thread.
	"""
	_tasks : Optional[list]
	_is_zombie : bool
	
	def __init__(self, main_queue:ThreadPoolScheduler):
		self._main_queue = main_queue
		self._mutex = Lock()
		self._ready = Lock()
		self._ready.acquire()
		self._tasks = None
		self._is_zombie = False
	
	def run(self):
		# This function exits with self._ready in the locked state. Always.
		while True:
			self._ready.acquire()
			with self._mutex:
				tasks = self._tasks
				self._tasks = None
			if tasks is None:
				return
			try:
				for task in tasks:
					if isinstance(task, BaseException):
						self._zombify()
						raise task
					else: task.proceed()
			finally:
				self._main_queue.unpin()
			

	def insert_task(self, task):
		assert task is not None
		with self._mutex:
			if self._is_zombie: return
			elif self._tasks: self._tasks.append(task)
			else:
				self._main_queue.pin()
				self._tasks = [task]
				self._ready.release()
	
	def _zombify(self):
		# Stop new messages arriving.
		# If any are pending, drop them and unpin once
		# to counteract the pin from insert_task.
		with self._mutex:
			self._is_zombie = True
			if self._tasks:
				self._tasks = None
				self._main_queue.unpin()
	
	def stop(self):
		# This can only happen when the pin count reaches zero,
		# which means (by definition) there are no messages in flight.
		with self._mutex:
			self._is_zombie = True
			assert self._tasks is None, self._tasks
			self._ready.release()
	
	def recover(self):
		# This can only run single-threaded on the main thread,
		# and only after stop has been called.
		assert self._tasks is None, self._tasks
		self._is_zombie = False
		if not self._ready.locked():
			self._ready.acquire()

MAIN_QUEUE = ThreadPoolScheduler(POOL_SIZE)

class Task:
	TASK_QUEUE = MAIN_QUEUE
	def enqueue(self):
		self.TASK_QUEUE.insert_task(self)
	
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
	
	_mailbox : Optional[list]
	def __init__(self):
		self._mutex = Lock()
		self._mailbox = None
		self._idle = True
	
	def proceed(self):
		with self._mutex:
			batch_of_messages = self._mailbox
			self._mailbox = None
		for message in batch_of_messages:
			self.handle(*message)
		with self._mutex:
			if self._mailbox:
				self.enqueue()
			else:
				self._idle = True
	
	def accept_message(self, method_name, args):
		with self._mutex:
			if self._mailbox is None:
				self._mailbox = []
			self._mailbox.append((method_name, args))
			if self._idle:
				self.enqueue()
				self._idle = False
	
	def handle(self, message, args):
		raise NotImplementedError(type(self))

class NativeObjectProxy(Actor):
	""" Wrap Python objects in one of these to use them as agents. """
	def __init__(self, principal, pin=False):
		super().__init__()
		self._principal = principal
		if pin:
			self.TASK_QUEUE = MAIN_QUEUE.main_thread
	def handle(self, method_name, args):
		method = getattr(self._principal, method_name)
		method(*args)


class SimpleTask(Task):
	def __init__(self, job, *args, **kwargs):
		assert callable(job)
		self._job = job
		self._args = args
		self._kwargs = kwargs
	def proceed(self):
		self._job(*self._args, **self._kwargs)

if __name__ == '__main__':
	MAIN_QUEUE.execute(SimpleTask(print, "Hello, Threading World!"))

