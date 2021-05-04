import sqlparse
from lark import Lark
from lark import Transformer

#raw = "QUERY scansum(MS2DATA) WHERE MS2PROD=271:MZDELTA=0.01 AND MS2PREC=500"
#raw = "QUERY scansum(MS2DATA) WHERE MS2PROD=271 AND MS2PREC=500"
raw = "QUERY scanrangesum(MS1DATA, TOLERANCE=0.1) WHERE MS1MZ=(QUERY scanmz(MS2DATA) WHERE MS2PROD=85.02820:MZDELTA=0.01 AND MS2NL=59.07350:MZDELTA=0.01):MZDELTA=0.01"
# statements = sqlparse.split(raw)

# print(statements)

# first = statements[0]

# print(sqlparse.format(first, reindent=True, keyword_case='upper'))

# parsed = sqlparse.parse(raw)[0]
# for token in parsed.tokens:
#     print("X", token)

msql_parser = Lark(open("msql.ebnf").read(), start='statement')
print(msql_parser)

tree = msql_parser.parse(raw)
print(tree.pretty())

class MyTransformer(Transformer):
   def condition(self, items):
      print(items)
      return "conditions"

print(MyTransformer().transform(tree))