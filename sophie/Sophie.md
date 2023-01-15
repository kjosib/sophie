# Grammar for Sophie (Germain)

Programming language inspired by Pascal and way too many other things.
Named for another French mathematician: Sophie Germain.
She was, among other things, a number theorist.

**This document is no mere reference.**
It is the very source-file from which Sophie's parser and scanner are generated.
It is up to date by definition.
(However, it might get out ahead of the evaluator.)

## Productions start

Quick primer on reading the grammar:

* All-upper-case represents a KEYWORD, which by the way has no semantic value.
* Punctuation in `'` quotes `'` are terminals which also have no semantic value.
* Things like `:foo` (words beginning with a colon) refer to parse actions, defined elsewhere. You can ignore them.
* The vertical-bar character `|` sits between equally-valid alternatives.
* Something like `optional(foo)` means a reference to the `optional` macro. These are defined later on in this file.
* You occasionally see a dot before a symbol, as in `.CASE`. You can ignore these dots.

```
start -> export_section import_section typedef_section define_section main_section END '.' :Module

export_section  -> EXPORT ':' comma_list(name) ';'             | :empty
import_section  -> IMPORT ':' semicolon_list(one_import)       | :empty
typedef_section -> TYPE ':' semicolon_list(type_declaration)   | :empty
define_section  -> DEFINE ':' semicolon_list(function)         | :empty
main_section    -> BEGIN ':' semicolon_list(expr)              | :empty

one_import -> short_string AS name
```

Since I'd like Sophie to support a unit/module system,
she needs a way to navigate namespaces. Here is that way:
```
reference -> name     :PlainReference
  | name '@' name     :QualifiedReference
```

**The grammar of type declarations**

At the moment, the intended semantics are typical of Hindley-Milner type algebras,
but with some niceties around variants / sum-types.

I've decided to do without nil as a special-case key-word for the time being.
That makes the type engine easier to work on.

```

type_declaration -> name optional(type_parameters) IS type_body :TypeDecl

type_parameters -> '[' comma_list(name) ']'

type_body -> simple_type | record_type | variant_type

record_type -> '(' comma_list(field) ')'   :RecordSpec

variant_type -> .CASE ':' .semicolon_list(subtype) ESAC  :VariantSpec

subtype  -> name record_type    :SubTypeSpec
          | name simple_type    :SubTypeSpec
          | name                :SubTypeSpec

field -> name ':' simple_type   :FormalParameter

simple_type -> named_type | arrow_type

named_type     -> reference optional(type_argument)              :TypeCall
arrow_type     -> '(' .comma_list(simple_type) ')' .'->' .simple_type              :ArrowSpec

type_argument  -> '[' comma_list(simple_type) ']'
```

**The general structure of a function:**
```
function -> name optional(parameter_list) annotation '=' expr optional(where_clause) :Function
where_clause -> WHERE semicolon_list(function) END name :WhereClause
```

Parameters to a function allow things to be implied.
You can leave off the type for a name,
or use a question-mark anywhere a type-name would normally go,
and the system will deal with it sensibly.
```
parameter_list  -> '(' comma_list(parameter) ')'
parameter       ->   name annotation   :FormalParameter
annotation ->  :nothing   |  ':' param_type

param_type -> reference             :TypeCall
| reference param_type_arg          :TypeCall
| .'?'                              :anonymous_type_variable
| '?' name                          :TypeParameter
| .param_type_arg .'->' .param_type :ArrowSpec

param_type_arg = '[' comma_list(param_type) ']'
```

**The Expression Grammar:**

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
| expr '(' comma_list(expr) ')' :Call
| expr list_expr :call_upon_list

list_expr -> '[' list_body ']'
list_body -> comma_list(expr) :ExplicitList

case_expr -> CASE semicolon_list(when_clause) else_clause ESAC :CaseWhen
when_clause -> .WHEN .expr THEN .expr
else_clause -> ELSE expr ';'
```
For a while, that was all. But then Sophie got type-matching based on variant-types:
```
match_expr -> CASE .subject ':' .semicolon_list(alternative) .optional(else_clause) ESAC  :match_expr
subject -> name | expr AS name :SubjectWithExpr
alternative -> pattern '->' expr optional(where_clause) :Alternative
pattern -> reference
```
Experience may later suggest expanding the `pattern` grammar, but this will do for now.

**Grammar Macros:**
```
comma_separated_list(x) -> x :first | _ ',' x :more
comma_list(x) ->  comma_separated_list(x) | comma_separated_list(x) ','
semicolon_list(x) ->  x ';' :first  | _ x ';' :more
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
%void_set UPPER
%void '(' ')' '[' ']' '.' ',' ';' ':' '=' '->' '@'
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
```
{wholeNumber}      :integer
{real}             :real
{alpha}{word}*     :word
\"[^"\v]*\"        :short_string
\s+|\#.*           :ignore
[<:>!=]=|[-=]>|{punct}  :punctuation
```


