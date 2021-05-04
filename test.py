import sqlparse
from lark import Lark
from lark import Transformer

raw = "QUERY scansum(MS2DATA) WHERE MS2PROD=271 AND MS2PREC=500 AND MS1MZ=100"
#raw = "QUERY scansum(MS2DATA) WHERE MS2PROD=271:MZDELTA=0.01:INTENSITYPERCENT>10 AND MS2PREC=500"
#raw = "QUERY scanrangesum(MS1DATA, TOLERANCE=0.1) WHERE MS1MZ=(QUERY scanmz(MS2DATA) WHERE MS2PROD=85.02820:MZDELTA=0.01 AND MS2NL=59.07350:MZDELTA=0.01):MZDELTA=0.01"
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
print(raw)

class MassQLToJSON(Transformer):
   # def fullcondition(self, items):
   #    print("X", items)
   #    return ""

   def qualifiermzdelta(self, items):
      return "qualifiermzdelta"
   
   def qualifierppmdelta(self, items):
      return "qualifierppmdelta"

   def ms2productcondition(self, items):
      return "ms2productcondition"

   def ms2precursorcondition(self, items):
      return "ms2precursorcondition"

   def ms2neutrallosscondition(self, items):
      return "ms2neutrallosscondition"
   
   def ms1mzcondition(self, items):
      return "ms1mzcondition"

   def qualifier(self, items):
      qualifier_dict = {}
      qualifier_dict["type"] = "qualifier"
      qualifier_dict["field"] = items[0]
      qualifier_dict["unit"] = "mz" #TODO Fix
      qualifier_dict["value"] = items[-1]
      return qualifier_dict

   def condition(self, items):
      condition_dict = {}
      condition_dict["type"] = items[0].children[0]
      condition_dict["value"] = items[1]
      #print("ZZZ", items, condition_dict)
      return condition_dict

   def fullcondition(self, items):
      """
      Defines the full set of qualifiers for a single constraint or all constraints

      Args:
          items ([type]): [description]

      Returns:
          [type]: [description]
      """
      print("AAA", items)

      if len(items) == 1:
         return items

      full_items_list = []
      for item in items:
         try:
            full_items_list += item
         except TypeError:
            pass

      print("BBB", full_items_list)

      return full_items_list

   def qualifierfields(self, items):
      return items[0]
   
   def string(self, s):
      (s,) = s
      return s[1:-1]
      
   def floating(self, n):
      (n,) = n
      return float(n)


   
   

print(MassQLToJSON().transform(tree))