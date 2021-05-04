import sqlparse
from lark import Lark

raw = "QUERY scansum(MS2DATA) WHERE MS2PROD=271 AND MS2PREC=500"
#raw = "QUERY scanrangesum(MS1DATA, TOLERANCE=0.1) WHERE MS1MZ=(QUERY scanmz(MS2DATA) WHERE MS2PROD=85.02820:MZDELTA=0.01 mz AND MS2NL=59.07350:MZDELTA=0.01 mz):MZDELTA=0.01"
# statements = sqlparse.split(raw)

# print(statements)

# first = statements[0]

# print(sqlparse.format(first, reindent=True, keyword_case='upper'))

# parsed = sqlparse.parse(raw)[0]
# for token in parsed.tokens:
#     print("X", token)



msql_parser = Lark(open("msql.ebnf").read(), start='statement')
print(msql_parser)

print(msql_parser.parse(raw).pretty())