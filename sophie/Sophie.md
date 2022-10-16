# Grammar for Sophie (Germain)

Toy programming language inspired by Pascal and way too many other things.
Named for another French mathematician: Sophie Germain.
She was, among other things, a number theorist.

There are three main goals:

1. Have fun.
2. Use a call-by-need evaluation strategy.
3. Do something cool with data type declarations.

## Productions start

Quick primer on reading the grammar:

* All-upper-case represents a KEYWORD, which by the way have no semantic value.
* Punctuation in `'` quotes `'` are terminals which also have no semantic value.
* Things like `:foo` refer to parse actions, defined elsewhere.
* Production rules without a parse action either are renaming rules or else create tuples.

```
start -> optional(exports) optional(imports) optional(types) optional(functions) :Module

exports -> EXPORT ':' comma_terminated_list(name) ';'
imports -> IMPORT ':' semicolon_terminated_list(one_import)
types -> TYPE ':' semicolon_terminated_list(type_declaration)
functions -> DEFINE ':' semicolon_terminated_list(function)

one_import -> short_string AS name

type_declaration -> name optional(type_parameters) IS type_body :TypeDecl
type_parameters -> '[' comma_terminated_list(name) ']'
type_body -> union_type | product_type | simple_type
union_type -> '{' seplist(type_summand, '|') '}'  :union_type
type_summand -> name optional(product_type) | NIL :nil_type
product_type -> '(' comma_terminated_list(field_definition) ')'
field_definition -> name ':' simple_type

simple_type -> '?' :type_implicit
| name  :type_name
| name '[' comma_terminated_list(simple_type) ']' :type_call
| simple_type '->' simple_type :arrow_type


function -> signature '=' expr optional(where_clause) :Function
signature -> name  optional(parameter_list) optional(return_type) :Signature
return_type -> '->' type
where_clause -> WHERE semicolon_terminated_list(function) END name :where_clause

parameter_list -> '(' comma_terminated_list(parameter) ')'
parameter -> name :param_inferred
| name ':' simple_type :param_constrained

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
```

This next bit tells the parser-generator how to tell which terminals have semantic value,
and therefore get passed to a production rule's action:
```
%void_set punct UPPER
```

## Definitions
These next two sections define the scanner.
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
As with the parser, the scan-actions are given by `:words`.
```
{wholeNumber}      :integer
{real}             :real
{alpha}{word}*     :word
\"[^"\v]*\"        :short_string
\s+|\#.*           :ignore
[<:>!=]=|[-=]>|{punct}  :punctuation
```


