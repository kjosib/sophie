# Grammar for Sophie (Germain)

*Programming language inspired by Pascal and way too many other things.*
*Named for another French mathematician: Sophie Germain.*
*She was, among other things, a number theorist.*

**This document is no mere reference:**

It is the very source-file from which Sophie's parser and scanner are generated.
It is up to date by definition.

**Quick primer on reading the grammar:**

* All-upper-case represents a reserved KEYWORD. Keywords in Sophie are not case-sensitive.
* Punctuation in `'` quotes `'` represents itself, and has no semantic value.
* Things like `:foo` (words beginning with a colon) refer to parse actions, defined elsewhere. You can ignore them.
* The vertical-bar character `|` sits between equally-valid alternatives.
* Something like `optional(foo)` means a reference to the `optional` macro. These are defined later on in this file.

Now let's begin.

-----

## Productions start

A Sophie program is composed of one or more modules, each in a separate file.

*Sophie originally required a module to end with `end.` a'la Pascal,*
*but people on the internet convinced me this was a bad idea.*

```
start -> module_definition
       | module_definition END '.'
```
Modules have sections for each major kind of thing they may contain.
Sections are all optional, but they come in a well-defined (and hopefully sensible) order.
Sophie uses keywords to introduce the different sections.

*There used to be a section called `export`, but it has not (yet) seemed worthwhile.*
```
module_definition -> import_section typedef_section assume_section define_section main_section :Module

import_section  -> IMPORT ':' semicolon_list(import_directive) | :empty
typedef_section -> TYPE ':' semicolon_list(type_definition)    | :empty
assume_section  -> ASSUME ':' semicolon_list(assumption)       | :empty
define_section  -> DEFINE ':' semicolon_list(term_definition)  | :empty
main_section    -> BEGIN ':' semicolon_list(expr)              | :empty
```

Since I'd like Sophie to support a unit/module system,
she needs a way to import modules and to navigate namespaces. Here is that way:
```
import_directive ->  optional(package) short_string alias symbol_imports  :ImportModule
package -> name '.'
symbol_imports -> optional(round_list(import_symbol))
import_symbol ->  name alias  :ImportSymbol
alias -> AS name | :nothing
```
-----

**The Grammar of Type-Definitions:**

Sophie makes a point of a strong and expressive type system.

```
type_definition  -> name type_parameters IS OPAQUE        :OpaqueSymbol
                  | name type_parameters IS record_spec   :RecordSymbol
                  | name type_parameters IS type_cases    :VariantSymbol
                  | name type_parameters IS simple_type   :TypeAliasSymbol
                  | name type_parameters IS role_spec     :RoleSymbol

type_parameters -> optional(square_list(name))

simple_type  -> generic(simple_type)
record_spec  -> round_list(field_dfn)                    :RecordSpec
type_cases   -> CASE ':' semicolon_list(tag_spec) ESAC
field_dfn    -> name ':' simple_type   :FieldDefinition

tag_spec  -> name record_spec    :RecordTag
           | name                :EnumTag

role_spec  -> ROLE ':' semicolon_list(ability) END
ability -> name optional(round_list(simple_type))      :Ability

```
*Sidebar:* The "simple" types in type declarations have a close cousin found in function declarations.
The commonality is as follows:
```
generic(item)  -> type_reference optional(square_list(item))   :TypeCall
                | round_list(item) '->' item              :ArrowSpec
                | '!' optional(round_list(item))          :MessageSpec

type_reference -> name     :PlainReference
       | name '@' name     :QualifiedReference
```
-----
**Type-Assumptions for Parameters:**

The concept is to apply consistent type-constraints to specific parameter-names across all functions in a module.
This supports the *don't repeat yourself* principle as applied to type-constraints in function signatures.
Mathematicians have been doing something similar in their books and papers for centuries,
so it's probably not a terrible idea.

*This may feel a bit like BASIC's `dim` statement, but it's entirely optional.*
```
assumption  ->  comma_list(name) ':' arg_type   :Assumption
```
If there's a conflict between the global assumption and the annotation at a particular function,
then the per-function annotation wins. And if there's neither, then the parameter is constrained
only by how you use it.

*One could imagine warning about unconstrained parameters, or even making it a stricture for large projects.*

-----

**Terms you can `define:`**
```
term_definition -> subroutine | actor_definition | operator_overload
```
Let's consider each in turn, starting with functions.

-----
**The general structure of a subroutine:**
```
subroutine   -> function | procedure
function     -> name formals annotation '=' expr where_clause   :UserFunction
procedure    -> TO name formals IS expr where_clause            :UserProcedure
formals      -> optional(round_list(parameter))
where_clause -> :nothing
              | WHERE semicolon_list(subroutine) END name       :WhereClause
```

Parameters to a function allow things to be implied.
You can leave off the type for a name,
or use a question-mark anywhere a type-name would normally go,
and Sophie will deal with it sensibly.
```
parameter  ->  stricture name annotation   :FormalParameter
stricture  ->  :nothing | STRICT
annotation ->  :nothing | ':' arg_type

arg_type -> generic(arg_type)
          | '?' name    :TypeCapture
          | '?'         :FreeType

```
I suppose it bears mention that all Sophie functions are implicitly generic
to whatever extent the body-expression can support.
However, if you specify parameter types, then the type-checker will check them and blame the caller for a mismatch.

-----

**Operator-Overloading in Sophie:**

You can define the meanings of (a small selection of) mathematical operators in conjunction with your data types:

```
operator -> '+' | '-' | '*' | '/' | '^' | DIV | MOD | '<=>' | '=='
operator_overload -> OPERATOR operator formals annotation '=' expr where_clause_for_operator     :UserOperator
where_clause_for_operator -> :nothing | WHERE semicolon_list(function) END OPERATOR operator     :WhereClause
```

Operator overloads must specify the (outermost) type of every parameter.
Also, at least one parameter to an overload ought to be defined in the same module.
For example, a module defining the arithmetic of complex numbers might contain something like:

    operator + (a:complex, b:complex) = complex(a.re+b.re, a.im+b.im);

Sophie *intentionally* will not support user-defined operators.
A small and standard set of operators imposes essentially no learning curve.
For anything else, named functions are recommended.

If you define the three-way comparison operator '<=>' for some particular type,
then it must return an `order` and you will get the six relational operators for free.
This makes sense when a total order is reasonable and natural.

If you define the equality operator `==` for a type, then it must return a `flag`
and you get `!=` for free. This is appropriate for when equivalence is well-defined,
but order makes no particular sense.

If you define both, the system will attempt to use the `==` definition in preference,
because that's assumed to be faster.

> *Note:*
>
> There is a well-defined total order for (IEEE 754 floating point)
> numbers including both positive and negative *NaN* values.
> The Sophie VM respects this ordering,
> but the tree-walker might not match the VM's behavior
> because Python does not preserve the sign of *NaN*.

-----

**The Expression Grammar:**

The bulk of the expression grammar covers the pure-functional aspects of the language.
```
expr -> integer | real | short_string | list_expr | conditional | case_expr | match_expr
      | '(' expr ')'
      | term_reference        :Lookup
      | expr '.' name         :FieldReference
      | '-' expr              :UnaryExp %prec UMINUS
      | expr '^' expr         :BinExp
      | expr '*' expr         :BinExp
      | expr '/' expr         :BinExp
      | expr DIV expr      :BinExp
      | expr MOD expr      :BinExp
      | expr '+' expr         :BinExp
      | expr '-' expr         :BinExp
      | expr '==' expr        :BinExp
      | expr '!=' expr        :BinExp
      | expr '<=' expr        :BinExp
      | expr '<' expr         :BinExp
      | expr '>' expr         :BinExp
      | expr '>=' expr        :BinExp
      | expr '<=>' expr       :BinExp
      | expr AND expr      :ShortCutExp
      | expr OR expr       :ShortCutExp
      | NOT expr            :UnaryExp
      | expr round_list(expr) :Call
      | expr list_expr        :call_upon_list
         
      | YES   :truth
      | NO    :falsehood
      
      | '{' comma_list(parameter) '|' expr '}'   :LambdaForm

term_reference -> name              :PlainReference
                | name '@' name     :QualifiedReference

conditional -> .expr .IF .expr ELSE .expr    :Cond

list_expr -> square_list(expr) :ExplicitList

case_expr -> CASE semicolon_list(when_clause) else_clause ESAC :CaseWhen
when_clause -> .WHEN .expr THEN .expr
else_clause -> ELSE expr ';'
```
For a while, that was all. But then Sophie got type-matching based on variant-types:
```
match_expr -> CASE subject hint OF semicolon_list(alternative) optional(else_clause) ESAC  :MatchExpr
subject -> expr alias    :Subject
hint -> :nothing | ':' type_reference
alternative -> name '->' expr where_clause :Alternative

```
Experience may later suggest expanding the `pattern` grammar, but this will do for now.

**Absurd Cases**

Type-case matches in Sophie must list every possible case for the subject of the match.
But sometimes there are cases which cannot happen in the first place.
Sophie's type-system is cool, but Sophie is not a proof system.
Instead, Sophie allows you to declare a case to be *absurd* along with a brief explanation.

The precise run-time behavior of reaching an absurdity is implementation-defined,
but should resemble whatever happens in case of division by zero.

```
alternative -> name '->' absurdity :absurdAlternative
absurdity -> ABSURD optional(short_string)  :Absurdity
```

Let's also provide for the `ELSE` case to be absurd.
This works for *both* `CASE ... OF` (type-case) and `CASE WHEN ...` (compound-conditional) forms:
```
else_clause -> ELSE absurdity ';'
```

-----

**Expressing Observable Behavior: Actors, Methods, and Procedures**

Pure functions may be easy to reason about,
but they're not much fun at parties because
they don't actually *do* anything.
Sophie needs a way to express action.

We can treat the notion of *action* as a special kind of value.
A program that does something observable *evaluates to an action,*
and the action happens in the process of this evaluation.

* The simplest action of all is to do nothing.
  An explicit `skip` action means Sophie does not need single-branch conditionals.
```
expr -> .SKIP       :Skip
```

* Sophie uses the *actor* model to interface with the world and to express concurrency.
* Everything that happens in **Sophie** is a result of sending messages to actors.
* User-Defined Actors have (private, mutable) state and behavior.
* All messages are delivered asynchronously and processed in the order received.

We can define actors this way:
```
actor_definition -> ACTOR name formals AS semicolon_list(procedure) END name  :UserActor
```
We'll need a way for actors to refer to themselves and their own private state:
```
term_reference -> .SELF       :SelfReference
                | MY name     :MemberReference

expr -> MY name ':=' expr     :AssignMember
```
We need a way to express the notion of a message addressed to some particular actor:
```
expr -> expr '!' name         :BindMethod
```
*If the message takes parameters, you'll call it like a procedure.*

It is also possible to invoke a freestanding procedure as a "background task":
```
expr -> '!' expr              :AsTask
```
**Sequencing Actions**

The so-called `do`-block lets you group actions into a sequence:
```
expr -> .with_actors .DO .semicolon_list(expr) END     :DoBlock
```
*Note that messages sent from a particular actor always arrive in the order sent,*
*although they may be interleaved with messages from other actors.*

**Creating Actors**

At the start of a `do`-block, you can cast new actors (the *with_actors* clause) to play their part:
```
with_actors -> :empty | CAST semicolon_list(new_actor)
new_actor   -> name IS expr   :NewActor
```
* The scope of an actor-name is from the point *after* its definition until the end of its do-block.
* No two actors created in the same do-block may have the same actor-name.

Thus, actors are created in a procedural order a'la side-effects.

-----
**Foreign Function Interface**

Most Sophie users won't need to worry about these rules,
so they get their own section.
```
import_directive -> FOREIGN short_string ffi_linkage ffi_body   :ImportForeign

ffi_linkage -> round_list(term_reference)     |    '(' ')' :empty    |    :nothing
ffi_body    -> WHERE semicolon_list(ffi_group)  END             |    :empty
ffi_group -> comma_list(ffi_symbol) ':' type_parameters simple_type  :FFI_Group
ffi_symbol  -> name                                 :FFI_Symbol
             | short_string AS name                 :FFI_Alias
             | short_string AS OPERATOR operator    :FFI_Operator
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
%nonassoc  '!'
%left '(' '[' '.'
%bogus UMINUS
%right '^'
%left '*' '/' DIV MOD
%left '+' '-'
%left '<' '<=' '==' '!=' '>=' '>'
%nonassoc '<=>'
%left NOT
%left AND OR
%nonassoc ':='
%right '->' IF ELSE
```

This next bit tells the parser-generator how to tell which terminals LACK
semantic value, and therefore DO NOT get passed to a production rule's action:
```
%void IMPORT TYPE ASSUME DEFINE BEGIN END TO AS MY
%void ACTOR ROLE CAST IS OF WHEN IF THEN ELSE
%void FOREIGN OPERATOR CASE ESAC OPAQUE WHERE
%void '(' ')' '[' ']' '.' ',' ';' ':' '=' '@' ':=' '|'
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
<=>                     :punctuation
```

There is not (yet?) any particular support for string-escapes as commonly found in languages like C or Java.
I'm not entirely sure it's important at all.
