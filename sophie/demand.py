"""
Just to be absolutely clear, this module does not have to be perfect.
It has to be fit for its purpose, which is to find the clearly-demanded.
This is allowed to underestimate. It's just not allowed to overestimate,
as that could potentially change the run-time semantics away from what
pure call-by-need (i.e. thunk-everything) would have done.
"""

from typing import Optional
from boozetools.support.foundation import Visitor, strongly_connected_components_hashable
from . import syntax
from .resolution import RoadMap, TopDown


def analyze_demand(roadmap:RoadMap):
	call_graph = DeterminedCallGraphPass(roadmap).graph
	outer = {udf:set() for udf in call_graph.keys()}
	for component in strongly_connected_components_hashable(call_graph):
		again = [True]
		while any(again):
			again = [DemandPass(udf, outer).grew for udf in component]


class DeterminedCallGraphPass(TopDown):
	graph : dict[Optional[syntax.UserFunction],set]
	
	def __init__(self, roadmap:RoadMap):
		self.graph = {None:set()}
		
		self.analyze_module(roadmap.preamble)
		for module in roadmap.each_module:
			self.analyze_module(module)
		
		del self.graph[None]
	
	def analyze_module(self, module:syntax.Module):
		for udf in module.all_fns:
			if isinstance(udf, syntax.UserFunction):
				self.graph[udf] = set()
		self.tour(module.top_subs)
		self.tour(module.actor_definitions)
		for expr in module.main:
			self.visit(expr, None)
	
	def tour(self, items):
		for i in items:
			self.visit(i)
	
	def visit_UserFunction(self, func:syntax.UserFunction):
		self.tour(func.where)
		self.visit(func.expr, func)
	
	def visit_UserActor(self, actor:syntax.UserActor):
		self.tour(actor.behaviors)
	
	def visit_UserProcedure(self, proc:syntax.UserProcedure):
		self.tour(proc.where)
		self.visit(proc.expr, None)
	
	def visit_Call(self, call: syntax.Call, src):
		if isinstance(call.fn_exp, syntax.Lookup):
			target = call.fn_exp.ref.dfn
			if isinstance(target, syntax.UserFunction):
				self.graph[src].add(target)
		elif isinstance(call.fn_exp, syntax.LambdaForm):
			self.graph[src].add(call.fn_exp.function)
		self.visit(call.fn_exp, src)
		for a in call.args:
			self.visit(a, src)
	
	def visit_Lookup(self, lu:syntax.Lookup, src):
		# If the dfn has no parameters, then make a link,
		# for it corresponds to calling a 0-ary function.
		dfn = lu.ref.dfn
		if isinstance(dfn, syntax.UserFunction):
			if not dfn.params:
				self.graph[src].add(dfn)
	
	def visit_LambdaForm(self, lf:syntax.LambdaForm, _src):
		self.visit_UserFunction(lf.function)

	def visit_MatchExpr(self, mx:syntax.MatchExpr, src):
		self.visit(mx.subject.expr, src)
		for alt in mx.alternatives:
			self.visit(alt, src)
		if mx.otherwise is not None:
			self.visit(mx.otherwise, src)

	def visit_Alternative(self, alt: syntax.Alternative, src):
		self.tour(alt.where)
		self.visit(alt.sub_expr, src)
	
	def visit_DoBlock(self, do:syntax.DoBlock, src):
		for actor in do.actors:
			self.visit(actor.expr, src)
		for step in do.steps:
			self.visit(step, src)
	
	def visit_AssignMember(self, am:syntax.AssignMember, src):
		self.visit(am.expr, src)

EMPTY = set()

def _possible(expr):
	return not isinstance(expr, syntax.Absurdity)

class DemandPass(Visitor):

	def __init__(self, udf:syntax.UserFunction, outer:dict[syntax.UserFunction,set[syntax.FormalParameter]]):
		self.grew = False
		self._outer = outer
		demanded = self.visit(udf.expr)
		
		for p in udf.params:
			if p in demanded:
				demanded.remove(p)
				if not p.is_strict:
					p.is_strict = True
					self.grew = True
		
		if demanded - outer[udf]:
			outer[udf].update(demanded)
			self.grew = True

	def _union(self, items):
		return EMPTY.union(*map(self.visit, items))

	def visit_Call(self, call: syntax.Call):
		if isinstance(call.fn_exp, syntax.Lookup):
			target = call.fn_exp.ref.dfn
			if isinstance(target, syntax.UserFunction):
				outer = self._outer.get(target, EMPTY)
				eager = [
					self.visit(actual)
					for formal, actual in zip(target.params, call.args)
					if formal.is_strict
				]
				return outer.union(*eager)
			elif isinstance(target, syntax.FFI_Alias):
				return self._union(call.args)
			elif isinstance(target, syntax.FormalParameter):
				return {target}
			elif isinstance(target, (syntax.TypeCase, syntax.Record)):
				return EMPTY
			elif isinstance(target, syntax.UserActor):
				# This is a rough spot. In general, the params to a syntax.UserActor
				# will eventually be strict, but the stricture happens later when the
				# template gets cast as an actor in a do-block. Until then, it works
				# like a record.
				return EMPTY
			else:
				assert False, type(target)  # How to analyze this target?
		elif isinstance(call.fn_exp, syntax.BindMethod):
			return self.visit(call.fn_exp) | self._union(call.args)
		return self.visit(call.fn_exp)

	def visit_MatchExpr(self, mx:syntax.MatchExpr):
		branches = [
			self.visit(alt.sub_expr)
			for alt in mx.alternatives
			if _possible(alt.sub_expr) 
		]
		if mx.otherwise is not None and _possible(mx.otherwise):
			branches.append(self.visit(mx.otherwise))
		return self.visit(mx.subject.expr) | set.intersection(*branches)

	def visit_Cond(self, cond:syntax.Cond):
		if_part = self.visit(cond.if_part)
		consequent = self.visit(cond.then_part)
		if _possible(cond.else_part):
			else_part = self.visit(cond.else_part)
			consequent.intersection_update(else_part)
		
		return if_part | consequent

	def visit_ShortCutExp(self, expr:syntax.ShortCutExp):
		return self.visit(expr.lhs)

	def visit_BinExp(self, bx:syntax.BinExp):
		return self.visit(bx.lhs) | self.visit(bx.rhs)

	def visit_UnaryExp(self, ux:syntax.UnaryExp):
		return self.visit(ux.arg)
	
	def visit_DoBlock(self, do:syntax.DoBlock):
		return self._union([actor.expr for actor in do.actors]) | self._union(do.steps)
	
	def visit_Lookup(self, lu:syntax.Lookup):
		dfn = lu.ref.dfn
		if isinstance(dfn, syntax.FormalParameter):
			return {dfn}
		elif isinstance(dfn, syntax.UserFunction) and not dfn.params:
			return self._outer.get(dfn, EMPTY)
		else:
			return EMPTY

	def visit_BindMethod(self, expr:syntax.BindMethod):
		return self.visit(expr.receiver)

	def visit_FieldReference(self, fr:syntax.FieldReference):
		return self.visit(fr.lhs)
	
	def visit_AsTask(self, task:syntax.AsTask):
		return self.visit(task.proc_ref)

	@staticmethod
	def visit_Literal(_):
		return EMPTY

	@staticmethod
	def visit_LambdaForm(_):
		return EMPTY

	@staticmethod
	def visit_ExplicitList(_):
		return EMPTY

	@staticmethod
	def visit_Skip(_):
		return EMPTY

	@staticmethod
	def visit_Absurdity(_):
		assert False, "Absurd cases ought not influence demand analysis."
	
	@staticmethod
	def visit_AssignMember(_):
		assert False, "Only behaviors can assign fields, but only functions are subject to this analysis."
