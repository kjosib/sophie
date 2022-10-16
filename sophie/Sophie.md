# Grammar for Sophie (Germain)

Toy programming language inspired by Pascal and way too many other things.
Named for another French mathematician: Sophie Germain.
She was, among other things, a number theorist.

There are three main goals:

1. Have fun.
2. Use a call-by-need evaluation strategy.
3. Do something cool with data type declarations.

## Productions start

Quick style primer:

* All-upper-case represents a KEYWORD.
* Things like `:foo` refer to parse actions, defined elsewhere.

```
start -> optional(exports) optional(imports) optional(types) optional(functions) :Module

exports -> EXPORT ':' comma_terminated_list(name) ';'
imports -> IMPORT ':' semicolon_terminated_list(one_import)
types -> TYPE ':' semicolon_terminated_list(type_decl)
functions -> DEFINE ':' semicolon_terminated_list(function)

one_import -> short_string AS name

type_decl -> name optional(generic) IS type :TypeDecl
generic -> '[' comma_terminated_list(name) ']'

function -> signature '=' expr optional(where_clause) :Function
signature -> name  optional(parameter_list) optional(return_type) :Signature
return_type -> '->' type
where_clause -> WHERE semicolon_terminated_list(function) END name :where_clause

type -> '?' :type_implicit
| name  :type_name
| name '[' comma_terminated_list(type) ']' :type_call
| type '->' type :arrow_type
| record_type
| union_type

parameter_list -> '(' comma_terminated_list(parameter) ')'
parameter -> name :param_inferred
| name ':' type :param_constrained

expr -> NIL | integer | real | short_string | list_expr | case_expr
| '(' expr ')'
| expr IF expr ELSE expr :Cond
| '-' expr :Negative %prec UMINUS
| expr '*' expr :Mul
| expr '/' expr :FloatDiv
| expr '%' expr :FloatMod
| expr DIV expr :IntDiv
| expr MOD expr :IntMod
| expr '+' expr :Add
| expr '-' expr :Sub
| expr '==' expr :EQ
| expr '!=' expr :EQ
| expr '<=' expr :LE
| expr '<' expr :LT
| expr '>' expr :GT
| expr '>=' expr :GE
| expr AND expr :LogicalAnd
| expr OR expr :LogicalOr
| NOT expr  :LogicalNot

| name
| name '(' comma_terminated_list(expr) ')' :Call
| name list_expr :ListCall

list_expr -> '[' list_body ']'
list_body -> comma_terminated_list(expr) :ExplicitList
list_body -> expr FOR name IN expr :Comprehension

case_expr -> CASE semicolon_terminated_list(when_clause) ELSE expr ';' ESAC :CaseWhen
when_clause -> WHEN expr THEN expr

```
And here are the grammar macros: 
```
seplist(x,s) -> x :first | ._ s .x :more
termlist(x,s) -> seplist(x,s) | seplist(x,s) s
comma_terminated_list(x) -> termlist(x,',')
semicolon_terminated_list(x) -> seplist(x,';') ';'
optional(x) -> :nothing | x
```

## Precedence

* Highest precedence comes first, like you learned in school.

```
%bogus UMINUS
%left '(' '.'
%right '^'
%left '*' '/' '%' DIV MOD
%left '+' '-'
%left '<' '<=' '==' '!=' '>=' '>'
%left NOT
%left AND OR

%right '->' IF ELSE

%void_set punct UPPER
```


## Definitions
```
leadingDigit    [1-9]
moreDigits      {digit}+(_{digit})*
wholeNumber     0|{leadingDigit}(_?{moreDigits})?
mantissa        {wholeNumber}(\.{moreDigits})?
exponent        [Ee][-+]?{wholeNumber}
real            {mantissa}{exponent}?
hex             {xdigit}+(_{xdigit}+)*
sigil           ([#$]|0[xX])
```
## Patterns
```
{wholeNumber}      :integer
{real}             :real
{alpha}{word}*     :word
\"[^"\v]*\"        :short_string
\s+                :ignore whitespace
\#.*               :ignore comments
[<:>!=]=|[-=]>|{punct}  :punctuation
```


