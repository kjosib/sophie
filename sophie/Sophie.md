# Grammar for Sophie (Germain)

Programming language inspired by Pascal and way too many other things.
Named for another French mathematician: Sophie Germain.
She was, among other things, a number theorist.

**This document is no mere reference.**
It is the very source-file from which Sophie's parser and scanner are generated.
It is up to date by definition.

## Productions start

Quick primer on reading the grammar:

* All-upper-case represents a KEYWORD, which by the way has no semantic value.
* Punctuation in `'` quotes `'` are terminals which also have no semantic value.
* Things like `:foo` (words beginning with a colon) refer to parse actions, defined elsewhere. You can ignore them.
* The vertical-bar character `|` sits between equally-valid alternatives.
* Something like `optional(foo)` means a reference to the `optional` macro. These are defined later on in this file.
* You occasionally see a dot before a symbol, as in `.CASE`. You can ignore these dots.

```
start -> module_definition
       | module_definition END '.'

module_definition -> export_section import_section typedef_section assume_section define_section main_section :Module

export_section  -> EXPORT ':' comma_list(name)                 | :empty
import_section  -> IMPORT ':' semicolon_list(import_directive) | :empty
typedef_section -> TYPE ':' semicolon_list(type_decl)          | :empty
assume_section  -> ASSUME ':' semicolon_list(assumption)       | :empty
define_section  -> DEFINE ':' semicolon_list(top_level)        | :empty
main_section    -> BEGIN ':' semicolon_list(expr)              | :empty

top_level -> function | agent_definition
```

Since I'd like Sophie to support a unit/module system,
she needs a way to import modules and to navigate namespaces. Here is that way:
```
import_directive ->  optional(package) short_string alias optional(round_list(import_symbol))   :ImportModule
package -> name '.'
import_symbol ->  name alias  :ImportSymbol
alias -> AS name | :nothing

reference -> name     :PlainReference
  | .SELF              :SelfReference
  | name '@' name     :QualifiedReference
```

**The grammar of type declarations**

```
type_decl  -> name type_parameters IS OPAQUE        :Opaque
            | name type_parameters IS simple_type   :TypeAlias
            | name type_parameters IS record_spec   :Record
            | name type_parameters IS variant_spec  :Variant
            | name type_parameters IS agent_spec    :Interface

type_parameters -> square_list(name) :type_parameters     | :empty

simple_type -> generic(simple_type) | arrow_of(simple_type)

record_spec  -> round_list(field_dfn)                    :RecordSpec

variant_spec -> CASE ':' semicolon_list(subtype) ESAC    :VariantSpec

field_dfn -> name ':' simple_type   :FormalParameter

subtype  -> name record_spec    :SubTypeSpec
          | name simple_type    :SubTypeSpec
          | name                :SubTypeSpec

agent_spec  -> AGENT ':' semicolon_list(method_type) END
method_type -> name optional(round_list(simple_type))      :MethodSpec

```
*Sidebar:* The "simple" types in type declarations have a close cousin found in function declarations.
The commonality is as follows:
```
generic(item)  -> reference optional(square_list(item))   :TypeCall
arrow_of(item) -> round_list(item) '->' item              :ArrowSpec
                | '!' optional(round_list(item))          :MessageSpec
```
-----
**Parameter Type Assumptions:**

This may feel a bit like BASIC's `dim` statement, but it's entirely optional.
The concept is to apply consistent type constraints to specific parameter-names across all functions in a module.
This supports the *don't repeat yourself* principle as applied to type-constraints in function signatures.
Mathematicians have been doing something similar in their books and papers for centuries,
so it's probably not a terrible idea.
```
assumption  ->  comma_list(name) ':' arg_type   :Assumption
```
If there's a conflict between the global assumption and the annotation at a particular function,
then the per-function annotation wins. And if there's neither, then the parameter is constrained
only by how you use it.

*Note 1: Everything just said depends on the type constraints actually working. They will, soon enough.*

*Note 2: One could imagine warning about unconstrained parameters, or even making it a stricture for large projects.*

-----
**The general structure of a function:**
```
function -> name formals annotation '=' expr where_clause     :UserFunction
where_clause -> :nothing | WHERE semicolon_list(function) END name                 :WhereClause
```

Parameters to a function allow things to be implied.
You can leave off the type for a name,
or use a question-mark anywhere a type-name would normally go,
and Sophie will deal with it sensibly.
```
formals -> optional(round_list(parameter))
parameter  ->   name annotation   :FormalParameter
annotation ->  :nothing | ':' arg_type

arg_type -> generic(arg_type) | arrow_of(arg_type)
          | '?' name    :ExplicitTypeVariable
          | '?'         :ImplicitTypeVariable

```
I suppose it bears mention that all Sophie functions are implicitly generic
to whatever extent the body-expression can support.

-----

**The Expression Grammar:**

The bulk of the expression grammar covers the pure-functional aspects of the language.

```
expr -> integer | real | short_string | list_expr | case_expr | match_expr
| '(' expr ')'
| expr '.' name :FieldReference
| .expr .IF .expr ELSE .expr :Cond
| '-' expr :Negative %prec UMINUS
| expr '^' expr :PowerOf
| expr '*' expr :Mul
| expr '/' expr :FloatDiv
| expr '%' expr :FloatMod
| .expr .DIV .expr :IntDiv
| .expr .MOD .expr :IntMod
| expr '+' expr :Add
| expr '-' expr :Sub
| expr '==' expr :EQ
| expr '!=' expr :NE
| expr '<=' expr :LE
| expr '<' expr :LT
| expr '>' expr :GT
| expr '>=' expr :GE
| .expr .AND .expr :LogicalAnd
| .expr .OR .expr :LogicalOr
| .NOT .expr  :LogicalNot

| reference :Lookup
| expr round_list(expr) :Call
| expr list_expr        :call_upon_list

| .YES   :truth
| .NO    :falsehood

list_expr -> square_list(expr) :ExplicitList

case_expr -> CASE semicolon_list(when_clause) else_clause ESAC :CaseWhen
when_clause -> .WHEN .expr THEN .expr
else_clause -> ELSE expr ';'
```
For a while, that was all. But then Sophie got type-matching based on variant-types:
```
match_expr -> CASE subject hint OF semicolon_list(alternative) optional(else_clause) ESAC  :MatchExpr
subject -> name     :simple_subject
  | expr AS name    :Subject
hint -> :nothing | ':' reference
alternative -> name '->' expr where_clause :Alternative

```
Experience may later suggest expanding the `pattern` grammar, but this will do for now.

**Absurd Cases**

Type-case matches in Sophie must list every variety of subtype for the subject of the match.
But sometimes there are cases which cannot happen in the first place.
Sophie's type-system is cool, but Sophie is not a proof system.
Instead, Sophie allows you to declare a case to be *absurd* along with a brief explanation.

The precise run-time behavior of reaching an absurdity is implementation-defined,
but should resemble whatever happens in case of division by zero.

```
alternative -> name '->' absurdity :absurdAlternative
absurdity -> .ABSURD .short_string  :Absurdity
```

-----

**Expressing Observable Behavior**

Pure functions may be easy to reason about,
but they're not much fun at parties because
they don't actually *do* anything.

Sophie needs a way to express action.

The general idea is that an action (or rather, a plan of action)
is just a special type of value which happens to express 
observable outcomes, with just a few extra production rules.

```
expr -> .SKIP       :Skip
      | '!' expr       :AsTask
      | expr '!' name       :BindMethod
      | MY name ':=' expr      :AssignField
      | .with_agents .DO .semicolon_list(expr) END     :DoBlock

with_agents -> :empty | CAST semicolon_list(new_agent)
new_agent -> name IS expr   :NewAgent
```

* The SKIP action does nothing, but means Sophie does not need single-branch conditionals.
  It can also have a place in case-expressions.
* The exclamation point (a.k.a. "bang`!`" operator) for sending messages is attested in a few languages.
  I suspect there's benefit to distinguishing method/message-binding from field access.
* If there's no left-hand side on the bang operator, then we can assume the "message" is to call a procedure asynchronously.
* The do-block expresses sequence, packaging several actions into one.

One sort of action remains: To create a new instance of some agent-class.
This may *look* like assignment, but Sophie attaches some rules:

* You can only create agents in the preamble of a do-block.
* The scope of an agent-name is from the point *after* its definition until the end of its do-block.
* No two agents created in the same do-block may have the same agent-name.

Thus, agents are created in procedural context, where it is perfectly fine to have side-effects.

*Semantic Note:*
Evidently the type system will need to distinguish between *agent-instance* and *agent-class.*

-----

**User-Defined Agent**

On balance an actor-like thing (`agent`, in Sophie parlance) has state and behavior.
For simplicity, let us *declare* that state with the same syntax as a record.
The chief difference is that agent state is mutable (and so cannot be shared).

There may be cause for stateless agents from time to time, so I'll make the state optional.
```
agent_definition -> AGENT name optional(round_list(field_dfn)) AS semicolon_list(behavior) END name  :UserAgent
behavior -> TO name formals IS expr   :Behavior
```
The name gets repeated at the end of an `agent` definition.
My motivation for this decision is the same as with functions that have subordinate `where` clauses.

At least for now, I'll not entertain nesting amongst agents or behaviors.
They're self-contained ... such as they are.

-----
**Foreign Function Interface**

Most Sophie users won't need to worry about these rules,
so they get their own section.
```
import_directive -> FOREIGN short_string ffi_linkage ffi_body   :ImportForeign

ffi_linkage -> round_list(reference)     |    '(' ')' :empty    |    :nothing
ffi_body    -> WHERE semicolon_list(ffi_group)  END             |    :empty
ffi_group   -> comma_list(ffi_symbol) ':' type_parameters simple_type  :FFI_Group
ffi_symbol  -> name                    :FFI_Symbol
             | name '@' short_string   :FFI_Alias
```

-----

**Grammar Macros:**

These grammar meta-rules make it easier to write the remainder of the grammar.
With any luck, their names are clear enough.
```
comma_separated_list(x) -> x :first | _ ',' x :more
comma_list(x) ->  comma_separated_list(x) | comma_separated_list(x) ','
semicolon_list(x) ->  x ';' :first  | _ x ';' :more
optional(x) -> :nothing | x

square_list(x) -> '[' comma_list(x) ']'
round_list(x) -> '(' comma_list(x) ')'
```

## Precedence

* Highest precedence comes first, like you learned in school.

```
%bogus UMINUS
%nonassoc  '!'
%left '(' '[' '.'
%right '^'
%left '*' '/' '%' DIV MOD
%left '+' '-'
%left '<' '<=' '==' '!=' '>=' '>'
%left NOT
%left AND OR
%nonassoc ':='
%right '->' IF ELSE
```

This next bit tells the parser-generator how to tell which terminals have semantic value,
and therefore get passed to a production rule's action:
```
%void_set UPPER
%void '(' ')' '[' ']' '.' ',' ';' ':' '=' '@' ':='
```

## Definitions
These next two sections define the scanner.
```
leadingDigit    [1-9]
moreDigits      {digit}+(_{digit}+)*
wholeNumber     0|{leadingDigit}(_?{moreDigits})?
mantissa        {wholeNumber}(\.{moreDigits})?
exponent        [Ee][-+]?{wholeNumber}
real            {mantissa}{exponent}?
hex             {xdigit}+(_{xdigit}+)*
sigil           ([#$]|0[xX])
```
## Patterns
As with the parser, the scan-actions are given by `:words`.
An action consisting of the `|` vertical-bar character means to use the identical action as the following rule.
```
{wholeNumber}           :integer
\${hex}+                :hexadecimal
{real}                  :real
[{alpha}_]{word}*       :word
\"[^"\v]*\"             |
\'[^'\v]*\'             :short_string
\s+|\#.*                :ignore
[<:>!=]=|[-=]>|{punct}  :punctuation
```

There is not (yet?) any particular support for string-escapes as commonly found in languages like C or Java.
I'm not entirely sure it's important at all.
