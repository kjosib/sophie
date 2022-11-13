# Grammar for Sophie (Germain)

Programming language inspired by Pascal and way too many other things.
Named for another French mathematician: Sophie Germain.
She was, among other things, a number theorist.

There are three main goals:

1. Have fun.
2. Use a call-by-need evaluation strategy.
3. Do something cool with data type declarations.

**This document is no mere reference.**
It is the very source-file from which Sophie's parser and scanner are generated.
It is up to date by definition.
(However, it might get out ahead of the evaluator.)

## Productions start

Quick primer on reading the grammar:

* All-upper-case represents a KEYWORD, which by the way has no semantic value.
* Punctuation in `'` quotes `'` are terminals which also have no semantic value.
* Things like `:foo` refer to parse actions, defined elsewhere. You can ignore them.
* Production rules without a parse action either are renaming rules or else create tuples.
* Something like `optional(foo)` means a reference to the `optional` macro. These are defined later on in this file.
* You occasionally see a dot before a symbol, as in `.NIL`. You can ignore these dots.

```
start -> optional(exports) optional(imports) optional(types) optional(functions) optional(main) END '.' :Module

exports -> EXPORT ':' comma_terminated_list(name) ';'
imports -> IMPORT ':' semicolon_terminated_list(one_import)
types -> TYPE ':' semicolon_terminated_list(type_declaration)
functions -> DEFINE ':' semicolon_terminated_list(function)
main -> BEGIN ':' semicolon_terminated_list(expr)

one_import -> short_string AS name
```

**The grammar of type declarations**

At the moment, the intended semantics are typical of Hindley-Milner type algebras,
with one quirk: the NIL symbol can be a member of any club that will have it.
I've not yet considered more general co/contravariance: That's for another time.

```
type_declaration -> name optional(type_parameters) IS type_body :TypeDecl
type_parameters -> '[' comma_terminated_list(name) ']'
type_body -> field_type | record_type | variant_type
record_type -> '(' comma_terminated_list(field) ')'   :RecordType
variant_type -> CASE semicolon_terminated_list(type_summand) ESAC  :VariantType
type_summand -> .NIL                :nil_type
              | name                :ordinal_type
              | name field_type     :TypeSummand
              | name record_type    :TypeSummand


field -> name ':' field_type :Parameter
field_type -> name
| name '[' comma_terminated_list(field_type) ']' :TypeCall
| FUNCTION comma_terminated_list(field_type) '->' field_type :ArrowType

```

Longer-term, I'd like to take on 


**The general structure of a function:**
```
function -> signature '=' expr optional(where_clause) :Function
signature -> name optional(parameter_list) optional(return_type) :Signature
return_type -> '->' param_type
where_clause -> WHERE semicolon_terminated_list(function) END name :WhereClause
```

Note that the parameters to a function allow things to be implied.
You can either leave off the type for a name,
or use a question-mark anywhere a type-name would normally go,
and the system will deal with it sensibly.
```
parameter_list -> '(' comma_terminated_list(parameter) ')'
parameter -> name ':' param_type :Parameter | name :param_inferred
param_type -> '?' :type_implicit
| name
| name '[' comma_terminated_list(param_type) ']' :TypeCall
| FUNCTION comma_terminated_list(param_type) '->' param_type :ArrowType
```

**The Expression Grammar:**

```
expr -> integer | real | short_string | list_expr | case_expr | match_expr
| .NIL :nil_value
| '(' expr ')'
| expr '.' name :FieldReference
| expr IF expr ELSE expr :Cond
| '-' expr :Negative %prec UMINUS
| expr '^' expr :PowerOf
| expr '*' expr :Mul
| expr '/' expr :FloatDiv
| expr '%' expr :FloatMod
| expr DIV expr :IntDiv
| expr MOD expr :IntMod
| expr '+' expr :Add
| expr '-' expr :Sub
| expr '==' expr :EQ
| expr '!=' expr :NE
| expr '<=' expr :LE
| expr '<' expr :LT
| expr '>' expr :GT
| expr '>=' expr :GE
| expr AND expr :LogicalAnd
| expr OR expr :LogicalOr
| NOT expr  :LogicalNot

| name :Lookup
| expr '(' comma_terminated_list(expr) ')' :Call
| expr list_expr :call_upon_list

list_expr -> '[' list_body ']'
list_body -> comma_terminated_list(expr) :ExplicitList

case_expr -> CASE semicolon_terminated_list(when_clause) else_clause ESAC :CaseWhen
when_clause -> WHEN expr THEN expr
else_clause -> ELSE expr ';'

match_expr -> CASE subject ':' semicolon_terminated_list(alternative) optional(else_clause) ESAC  :match_expr
subject -> name | expr AS name :SubjectWithExpr
alternative -> pattern '->' expr  :Alternative
pattern -> name  | .NIL :NilToken
```
Experience may later suggest expanding the `pattern` grammar, but this will do for now.

**Grammar Macros:**
```
seplist(x,s) -> x :first | ._ s .x :more
termlist(x,s) -> seplist(x,s) | .seplist(x,s) s
comma_terminated_list(x) -> termlist(x,',')
semicolon_terminated_list(x) -> seplist(x,';') ';'
optional(x) -> :nothing | x
```

## Precedence

* Highest precedence comes first, like you learned in school.

```
%bogus UMINUS
%left '(' '[' '.'
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


