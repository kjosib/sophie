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
start -> module_definition
       | module_definition END '.'

module_definition -> export_section import_section typedef_section define_section main_section :Module

export_section  -> EXPORT ':' comma_list(name) ';'             | :empty
import_section  -> IMPORT ':' semicolon_list(import_directive) | :empty
typedef_section -> TYPE ':' semicolon_list(type_declaration)   | :empty
define_section  -> DEFINE ':' semicolon_list(function)         | :empty
main_section    -> BEGIN ':' semicolon_list(expr)              | :empty
```

Since I'd like Sophie to support a unit/module system,
she needs a way to import modules and to navigate namespaces. Here is that way:
```
import_directive -> short_string AS name  :ImportModule

reference -> name     :PlainReference
  | name '@' name     :QualifiedReference
```

**The grammar of type declarations**

```

type_declaration -> type_name_is OPAQUE         :Opaque
                  | type_name_is simple_type    :TypeAlias
                  | type_name_is record_spec    :Record
                  | type_name_is variant_spec   :Variant

type_name_is -> name type_parameters IS   :Generic
type_parameters -> optional_square_list(name)

record_spec -> round_list(field)  :RecordSpec
field -> name ':' simple_type   :FormalParameter

variant_spec -> CASE ':' semicolon_list(subtype) ESAC

subtype  -> name record_spec    :SubTypeSpec
          | name simple_type    :SubTypeSpec
          | name                :SubTypeSpec

simple_type -> named_type | arrow_type
named_type  -> reference optional_square_list(simple_type)    :TypeCall
arrow_type  -> round_list(simple_type) '->' simple_type       :ArrowSpec
```
**Caveat:** Opaque type declarations should not have type-parameters.

**The general structure of a function:**
```
function -> name optional(round_list(parameter)) annotation '=' expr optional(where_clause)    :UserDefinedFunction
where_clause -> WHERE semicolon_list(function) END name :WhereClause
```

Parameters to a function allow things to be implied.
You can leave off the type for a name,
or use a question-mark anywhere a type-name would normally go,
and Sophie will deal with it sensibly.
```
parameter  ->   name annotation   :FormalParameter
annotation ->  :nothing | ':' arg_type

arg_type ->  '?'                               :ImplicitTypeVariable
  | '?' name                                   :ExplicitTypeVariable
  | reference optional_square_list(arg_type)   :TypeCall
  | round_list(arg_type) '->' arg_type         :ArrowSpec
```
I suppose it bears mention that all Sophie functions are implicitly generic
to whatever extent the body-expression can support.


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

| .YES   :truth
| .NO    :falsehood

list_expr -> square_list(expr) :ExplicitList

case_expr -> CASE semicolon_list(when_clause) else_clause ESAC :CaseWhen
when_clause -> .WHEN .expr THEN .expr
else_clause -> ELSE expr ';'
```
For a while, that was all. But then Sophie got type-matching based on variant-types:
```
match_expr -> CASE subject optional(type_hint) OF semicolon_list(alternative) optional(else_clause) ESAC  :MatchExpr
subject -> name     :simple_subject
  | expr AS name    :Subject
type_hint -> ':' reference
alternative -> pattern '->' expr optional(where_clause) :Alternative
pattern -> reference
```
Experience may later suggest expanding the `pattern` grammar, but this will do for now.

-----

**Foreign Function Interface**

Most Sophie users won't need to worry about these rules,
so they get their own section.
```
import_directive -> FOREIGN short_string WHERE semicolon_list(ffi_group) END   :ImportForeign

ffi_group -> comma_list(ffi_symbol) ':' type_parameters simple_type  :FFI_Group
ffi_symbol -> name                    :FFI_Symbol
            | name '@' short_string   :FFI_Alias
```

One caveat: ImplicitTypeVariable is not acceptable in the arg_type mentioned in an FFI_Group.

-----

**Grammar Macros:**

These grammar meta-rules make it easier to write the remainder of the grammar.
With any luck, their names are clear enough.
```
comma_separated_list(x) -> x :first | _ ',' x :more
comma_list(x) ->  comma_separated_list(x) | comma_separated_list(x) ','
semicolon_list(x) ->  x ';' :first  | _ x ';' :more
optional(x) -> :nothing | x

optional_square_list(x) -> :empty | square_list(x) 
square_list(x) -> '[' comma_list(x) ']'
round_list(x) -> '(' comma_list(x) ')'
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
%void '(' ')' '[' ']' '.' ',' ';' ':' '=' '@'
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
[{alpha}_]{word}*     :word
\"[^"\v]*\"        :short_string
\s+|\#.*           :ignore
[<:>!=]=|[-=]>|{punct}  :punctuation
```


