import sqlparse
from lark import Lark
from lark import Transformer

#raw = "QUERY scansum(MS2DATA) WHERE MS2PROD=271 AND MS2PREC=500"
#raw = "QUERY scansum(MS2DATA) WHERE MS2PROD=271:MZDELTA=0.01 AND MS2PREC=500"
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

class MassQLToJSON(Transformer):
   # def fullcondition(self, items):
   #    print("X", items)
   #    return ""

   def qualifiermzdelta(self, items):
      return "qualifiermzdelta"
   
   def qualifierppmdelta(self, items):
      return "qualifierppmdelta"

   def qualifier(self, items):
      qualifier_dict = {}
      qualifier_dict["type"] = "qualifier"
      qualifier_dict["unit"] = "mz" #TODO Fix
      qualifier_dict["value"] = items[-1]
      print("Y", qualifier_dict)
      return qualifier_dict
   
   def string(self, s):
      print("STRING", s)
      (s,) = s
      return s[1:-1]
      
   def floating(self, n):
      (n,) = n
      return float(n)


   
   

print(MassQLToJSON().transform(tree))