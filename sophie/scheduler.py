"""
This is the simple task-queue version of a scheduler.
At some point I may do a work-stealing version for fun,
but the semantics of the language are the same regardless.
"""
import collections, threading, traceback

POOL_SIZE = 3

class ThreadPoolScheduler:
	"""
	Responsible for the main task queue and pool of worker threads.
	Can also trigger shut-down. System threads can prevent that by
	adjusting the number of 
	"""

	def __init__(self, nr_workers:int):
		self._mutex = threading.Lock()
		self._all_done = threading.Lock()
		self._all_done.acquire()
		self._tasks = collections.deque()
		self._idle = collections.deque()
		self._nr_busy = nr_workers
		for i in range(nr_workers):
			threading.Thread(target=self._worker, daemon=True, name="worker thread " + str(i)).start()
		self._all_done.acquire()

	def perform(self, task):
		""" The main thread should call this to kick off a job. """
		self.insert_task(task)
		self._all_done.acquire()

	def insert_task(self, task):
		""" Individual tasks will use this to  """
		self._mutex.acquire()
		self._tasks.append(task)
		if self._idle:
			# Let's do an idle-stack rather than round-robin:
			self._idle.pop().release()
		self._mutex.release()

	def _worker(self):
		notify_me = threading.Lock()
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
			self._all_done.release()

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

MAIN_QUEUE = ThreadPoolScheduler(POOL_SIZE)

class SampleTask:
	@staticmethod
	def proceed():
		print("Hello, Threading World!")

if __name__ == '__main__':
	MAIN_QUEUE.perform(SampleTask())

